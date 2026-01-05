import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import numpy as np

# Page configuration
st.set_page_config(
    page_title="Watchlist Fever Accuracy Evaluation",
    page_icon="🌡️",
    layout="wide"
)

# Fever thresholds
FEVER_THRESHOLDS = {
    'Calf': 39.7,      # 0-14 months
    'Heifer': 40.1,    # 15-50 months
    'Cow': 40.3        # 51-150 months
}

def categorize_age(age_in_days):
    """Categorize animal by age"""
    age_in_months = age_in_days / 30
    if age_in_months <= 14:
        return 'Calf'
    elif age_in_months <= 50:
        return 'Heifer'
    else:
        return 'Cow'

def get_fever_threshold(age_category):
    """Get fever threshold for age category"""
    return FEVER_THRESHOLDS.get(age_category, 40.3)

def check_fever_sustained(temp_series, threshold, min_hours=3):
    """Check if fever is sustained for minimum hours"""
    # Assuming 15-minute intervals (4 readings per hour)
    min_readings = min_hours * 4
    
    # Check for consecutive readings above threshold
    above_threshold = temp_series >= threshold
    consecutive_count = 0
    max_consecutive = 0
    
    for val in above_threshold:
        if val:
            consecutive_count += 1
            max_consecutive = max(max_consecutive, consecutive_count)
        else:
            consecutive_count = 0
    
    return max_consecutive >= min_readings, max_consecutive / 4  # Return hours

def evaluate_wl_entry(sensor_df, animal_id, date_in, age_category):
    """Evaluate if WL entry was accurate based on temperature at entry time"""
    threshold = get_fever_threshold(age_category)
    
    # Get temperature readings around entry time (±30 minutes window)
    date_in_dt = pd.to_datetime(date_in)
    window_start = date_in_dt - pd.Timedelta(minutes=30)
    window_end = date_in_dt + pd.Timedelta(minutes=30)
    
    entry_temps = sensor_df[
        (sensor_df['id'] == animal_id) &
        (sensor_df['datetime'] >= window_start) &
        (sensor_df['datetime'] <= window_end)
    ]['temp']
    
    if len(entry_temps) == 0:
        return 'Unknown', None, 'No sensor data available'
    
    max_temp = entry_temps.max()
    avg_temp = entry_temps.mean()
    
    if max_temp >= threshold:
        return 'Valid', max_temp, f'Temp {max_temp:.1f}°C ≥ threshold {threshold}°C'
    else:
        return 'Invalid', max_temp, f'No fever spike (max: {max_temp:.1f}°C < {threshold}°C)'

def evaluate_fever_sustainability(sensor_df, animal_id, date_in, date_out, age_category):
    """Check if fever was sustained during WL period"""
    threshold = get_fever_threshold(age_category)
    
    date_in_dt = pd.to_datetime(date_in)
    date_out_dt = pd.to_datetime(date_out)
    
    period_temps = sensor_df[
        (sensor_df['id'] == animal_id) &
        (sensor_df['datetime'] >= date_in_dt) &
        (sensor_df['datetime'] <= date_out_dt)
    ]['temp']
    
    if len(period_temps) == 0:
        return 'Unknown', 0, 'No sensor data available'
    
    is_sustained, hours = check_fever_sustained(period_temps, threshold)
    
    if is_sustained:
        return 'Sustained', hours, f'Fever sustained for {hours:.1f} hours'
    else:
        return 'Not Sustained', hours, f'Fever only sustained for {hours:.1f}h (< 3h required)'

def evaluate_wl_exit(sensor_df, animal_id, date_out, age_category):
    """Evaluate if WL exit was accurate (fever resolved)"""
    threshold = get_fever_threshold(age_category)
    
    date_out_dt = pd.to_datetime(date_out)
    window_end = date_out_dt + pd.Timedelta(hours=6)
    
    post_exit_temps = sensor_df[
        (sensor_df['id'] == animal_id) &
        (sensor_df['datetime'] > date_out_dt) &
        (sensor_df['datetime'] <= window_end)
    ]['temp']
    
    if len(post_exit_temps) == 0:
        return 'Unknown', None, 'No sensor data available'
    
    max_temp = post_exit_temps.max()
    avg_temp = post_exit_temps.mean()
    
    # Check if fever persists (≥40°C for 2-3 hours)
    high_fever_readings = (post_exit_temps >= 40.0).sum()
    hours_high_fever = high_fever_readings / 4  # Assuming 15-min intervals
    
    if max_temp < threshold:
        return 'Accurate', max_temp, f'Fever resolved (max: {max_temp:.1f}°C)'
    elif hours_high_fever >= 2:
        return 'Premature', max_temp, f'Fever persists (≥40°C for {hours_high_fever:.1f}h)'
    else:
        return 'Borderline', max_temp, f'Elevated temp but brief ({max_temp:.1f}°C)'

def analyze_watchlist(sensor_df, watchlist_df):
    """Comprehensive WL analysis"""
    results = []
    
    for _, wl_row in watchlist_df.iterrows():
        animal_id = wl_row['animalId']
        date_in = wl_row['dateIn']
        date_out = wl_row['dateOut']
        reason = wl_row['reason']
        highest_score = wl_row['highestScore']
        
        # Get animal's age category
        animal_sensor = sensor_df[sensor_df['id'] == animal_id]
        if len(animal_sensor) == 0:
            continue
            
        age_category = animal_sensor['age_category'].iloc[0]
        
        # Skip cows for now
        if age_category == 'Cow':
            continue
        
        # Evaluate entry
        entry_accuracy, entry_temp, entry_detail = evaluate_wl_entry(
            sensor_df, animal_id, date_in, age_category
        )
        
        # Evaluate sustainability
        sustained_status, sustained_hours, sustained_detail = evaluate_fever_sustainability(
            sensor_df, animal_id, date_in, date_out, age_category
        )
        
        # Evaluate exit
        exit_accuracy, exit_temp, exit_detail = evaluate_wl_exit(
            sensor_df, animal_id, date_out, age_category
        )
        
        results.append({
            'Animal ID': animal_id,
            'Age Category': age_category,
            'Date In': date_in,
            'Date Out': date_out,
            'Reason': reason,
            'Highest Score': highest_score,
            'Entry Accuracy': entry_accuracy,
            'Entry Temp': entry_temp,
            'Entry Detail': entry_detail,
            'Fever Sustained': sustained_status,
            'Sustained Hours': sustained_hours,
            'Sustained Detail': sustained_detail,
            'Exit Accuracy': exit_accuracy,
            'Exit Temp': exit_temp,
            'Exit Detail': exit_detail
        })
    
    return pd.DataFrame(results)

def plot_animal_timeline(sensor_df, animal_id, date_in, date_out, age_category):
    """Create detailed timeline plot for an animal"""
    date_in_dt = pd.to_datetime(date_in)
    date_out_dt = pd.to_datetime(date_out)
    
    # Get data from 2 days before to 3 days after
    start_date = date_in_dt - pd.Timedelta(days=2)
    end_date = date_out_dt + pd.Timedelta(days=3)
    
    animal_data = sensor_df[
        (sensor_df['id'] == animal_id) &
        (sensor_df['datetime'] >= start_date) &
        (sensor_df['datetime'] <= end_date)
    ].sort_values('datetime')
    
    if len(animal_data) == 0:
        return None
    
    threshold = get_fever_threshold(age_category)
    
    # Create figure
    fig = go.Figure()
    
    # Add temperature line
    fig.add_trace(go.Scatter(
        x=animal_data['datetime'],
        y=animal_data['temp'],
        mode='lines+markers',
        name='Body Temperature',
        line=dict(color='#FF6B6B', width=2),
        marker=dict(size=4)
    ))
    
    # Add fever threshold line
    fig.add_hline(
        y=threshold,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Fever Threshold ({threshold}°C)",
        annotation_position="right"
    )
    
    # Add herd average temperature
    if 'aveHerdTemp' in animal_data.columns:
        fig.add_trace(go.Scatter(
            x=animal_data['datetime'],
            y=animal_data['aveHerdTemp'],
            mode='lines',
            name='Herd Average',
            line=dict(color='#95E1D3', width=1, dash='dot'),
            opacity=0.6
        ))
    
    # Add WL period shading
    fig.add_vrect(
        x0=date_in_dt, x1=date_out_dt,
        fillcolor="yellow", opacity=0.2,
        layer="below", line_width=0
    )
    
    # Add vertical lines for entry and exit using shapes
    fig.add_shape(
        type="line",
        x0=date_in_dt, x1=date_in_dt,
        y0=0, y1=1,
        yref="paper",
        line=dict(color="green", width=2, dash="dash")
    )
    
    fig.add_shape(
        type="line",
        x0=date_out_dt, x1=date_out_dt,
        y0=0, y1=1,
        yref="paper",
        line=dict(color="orange", width=2, dash="dash")
    )
    
    # Add annotations separately
    fig.add_annotation(
        x=date_in_dt,
        y=1.05,
        yref="paper",
        text="WL Entry",
        showarrow=False,
        font=dict(color="green", size=12),
        xanchor="center"
    )
    
    fig.add_annotation(
        x=date_out_dt,
        y=1.05,
        yref="paper",
        text="WL Exit",
        showarrow=False,
        font=dict(color="orange", size=12),
        xanchor="center"
    )
    
    fig.add_annotation(
        x=date_in_dt + (date_out_dt - date_in_dt) / 2,
        y=1.08,
        yref="paper",
        text="On Watchlist",
        showarrow=False,
        font=dict(color="black", size=11),
        xanchor="center"
    )
    
    # Add event markers if present
    events = animal_data[animal_data['event'].notna()]
    if len(events) > 0:
        fig.add_trace(go.Scatter(
            x=events['datetime'],
            y=events['temp'],
            mode='markers',
            name='Health Events',
            marker=dict(
                size=12,
                symbol='star',
                color='red',
                line=dict(color='darkred', width=2)
            ),
            text=events['event'],
            hovertemplate='%{text}<br>%{y:.1f}°C<extra></extra>'
        ))
    
    fig.update_layout(
        title=f'Animal {animal_id} - Temperature Timeline ({age_category})',
        xaxis_title='Date/Time',
        yaxis_title='Temperature (°C)',
        hovermode='x unified',
        height=500,
        showlegend=True,
        template='plotly_white'
    )
    
    return fig

# Main App
st.title("🌡️ Watchlist Fever Accuracy Evaluation Dashboard")
st.markdown("### Validate Watchlist entries using age-based fever thresholds")

# Sidebar for file upload
with st.sidebar:
    st.header("📁 Data Upload")
    
    sensor_file = st.file_uploader("Upload Sensor Data CSV", type=['csv'])
    watchlist_file = st.file_uploader("Upload Watchlist Data CSV", type=['csv'])
    
    st.markdown("---")
    st.markdown("### 🌡️ Fever Thresholds")
    st.markdown(f"- **Calves (0-14 months):** {FEVER_THRESHOLDS['Calf']}°C")
    st.markdown(f"- **Heifers (15-50 months):** {FEVER_THRESHOLDS['Heifer']}°C")
    st.markdown(f"- **Cows (51-150 months):** {FEVER_THRESHOLDS['Cow']}°C")
    
    st.markdown("---")
    st.markdown("### Validation Rules")
    st.markdown("- **Entry:** Temp ≥ threshold at dateIn")
    st.markdown("- **Sustained:** Fever ≥ 3 hours")
    st.markdown("- **Exit:** Temp < threshold after dateOut")

if sensor_file and watchlist_file:
    # Extract farm ID from filename
    farm_id = "Unknown"
    if sensor_file.name:
        # Try to extract farm ID from various patterns
        if 'farm-id-' in sensor_file.name:
            match = sensor_file.name.split('farm-id-')[1].split('.')[0].split('-')[0]
            farm_id = match
        elif 'farm_id_' in sensor_file.name:
            match = sensor_file.name.split('farm_id_')[1].split('.')[0].split('_')[0]
            farm_id = match
        elif 'farmId' in sensor_file.name:
            match = sensor_file.name.split('farmId')[1].split('.')[0].split('-')[0]
            farm_id = match
    
    # Load data
    with st.spinner("Loading data..."):
        sensor_df = pd.read_csv(sensor_file)
        watchlist_df = pd.read_csv(watchlist_file)
        
        # Parse datetime
        sensor_df['datetime'] = pd.to_datetime(sensor_df['datetime'])
        watchlist_df['dateIn'] = pd.to_datetime(watchlist_df['dateIn'])
        watchlist_df['dateOut'] = pd.to_datetime(watchlist_df['dateOut'])
        
        # Add age category if not present
        if 'age_category' not in sensor_df.columns:
            sensor_df['age_category'] = sensor_df['ageInDays'].apply(categorize_age)
    
    # Analyze
    with st.spinner("Analyzing watchlist accuracy..."):
        results_df = analyze_watchlist(sensor_df, watchlist_df)
    
    if len(results_df) == 0:
        st.error("No results generated. Check if animal IDs match between files.")
    else:
        # Summary metrics
        st.header("📊 Overall Performance Summary")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("🏢 Farm ID", farm_id)
        
        with col2:
            total_entries = len(results_df)
            st.metric("Total WL Entries", total_entries)
        
        with col3:
            valid_entries = (results_df['Entry Accuracy'] == 'Valid').sum()
            entry_accuracy_pct = (valid_entries / total_entries * 100) if total_entries > 0 else 0
            st.metric("Valid Entries", f"{valid_entries} ({entry_accuracy_pct:.1f}%)")
        
        with col4:
            sustained_count = (results_df['Fever Sustained'] == 'Sustained').sum()
            sustained_pct = (sustained_count / total_entries * 100) if total_entries > 0 else 0
            st.metric("Sustained Fever", f"{sustained_count} ({sustained_pct:.1f}%)")
        
        with col5:
            accurate_exits = (results_df['Exit Accuracy'] == 'Accurate').sum()
            exit_accuracy_pct = (accurate_exits / total_entries * 100) if total_entries > 0 else 0
            st.metric("Accurate Exits", f"{accurate_exits} ({exit_accuracy_pct:.1f}%)")
        
        # Age group breakdown
        st.header("📈 Performance by Age Group")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Entry accuracy by age
            entry_by_age = results_df.groupby(['Age Category', 'Entry Accuracy']).size().reset_index(name='Count')
            fig_entry = px.bar(
                entry_by_age,
                x='Age Category',
                y='Count',
                color='Entry Accuracy',
                title='Entry Accuracy by Age Group',
                color_discrete_map={'Valid': '#2ECC71', 'Invalid': '#E74C3C', 'Unknown': '#95A5A6'}
            )
            st.plotly_chart(fig_entry, use_container_width=True)
        
        with col2:
            # Exit accuracy by age
            exit_by_age = results_df.groupby(['Age Category', 'Exit Accuracy']).size().reset_index(name='Count')
            fig_exit = px.bar(
                exit_by_age,
                x='Age Category',
                y='Count',
                color='Exit Accuracy',
                title='Exit Accuracy by Age Group',
                color_discrete_map={'Accurate': '#2ECC71', 'Premature': '#E74C3C', 
                                   'Borderline': '#F39C12', 'Unknown': '#95A5A6'}
            )
            st.plotly_chart(fig_exit, use_container_width=True)
        
        # Filters
        st.header("🔍 Detailed Results")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            age_filter = st.multiselect(
                "Filter by Age Category",
                options=results_df['Age Category'].unique(),
                default=results_df['Age Category'].unique()
            )
        
        with col2:
            entry_filter = st.multiselect(
                "Filter by Entry Accuracy",
                options=results_df['Entry Accuracy'].unique(),
                default=results_df['Entry Accuracy'].unique()
            )
        
        with col3:
            reason_filter = st.multiselect(
                "Filter by Reason",
                options=results_df['Reason'].unique(),
                default=results_df['Reason'].unique()
            )
        
        # Apply filters
        filtered_df = results_df[
            (results_df['Age Category'].isin(age_filter)) &
            (results_df['Entry Accuracy'].isin(entry_filter)) &
            (results_df['Reason'].isin(reason_filter))
        ]
        
        # Display results table with color coding
        def color_accuracy(val):
            if val == 'Valid' or val == 'Accurate' or val == 'Sustained':
                return 'background-color: #D5F4E6'
            elif val == 'Invalid' or val == 'Premature' or val == 'Not Sustained':
                return 'background-color: #FADBD8'
            elif val == 'Borderline':
                return 'background-color: #FCF3CF'
            else:
                return 'background-color: #EAECEE'
        
        styled_df = filtered_df[['Animal ID', 'Age Category', 'Date In', 'Date Out', 
                                 'Reason', 'Highest Score', 'Entry Accuracy', 
                                 'Fever Sustained', 'Exit Accuracy']].style.applymap(
            color_accuracy,
            subset=['Entry Accuracy', 'Fever Sustained', 'Exit Accuracy']
        )
        
        st.dataframe(styled_df, use_container_width=True, height=400)
        
        # Download button
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="📥 Download Results as CSV",
            data=csv,
            file_name="watchlist_accuracy_evaluation.csv",
            mime="text/csv"
        )
        
        # Detailed drill-down
        st.header("🔬 Detailed Animal Analysis")
        
        selected_animal = st.selectbox(
            "Select Animal ID to view detailed timeline:",
            options=sorted(filtered_df['Animal ID'].unique())
        )
        
        if selected_animal:
            # Get all WL entries for this animal
            animal_entries = filtered_df[filtered_df['Animal ID'] == selected_animal].reset_index(drop=True)
            
            if len(animal_entries) > 1:
                # Multiple entries - let user select which one
                wl_options = []
                for idx, row in animal_entries.iterrows():
                    date_in_str = pd.to_datetime(row['Date In']).strftime('%Y-%m-%d %H:%M')
                    date_out_str = pd.to_datetime(row['Date Out']).strftime('%Y-%m-%d %H:%M')
                    wl_options.append(f"Entry {idx+1}: {date_in_str} to {date_out_str} ({row['Reason']})")
                
                selected_wl_idx = st.selectbox(
                    f"Animal {selected_animal} has {len(animal_entries)} watchlist entries. Select one:",
                    options=range(len(wl_options)),
                    format_func=lambda x: wl_options[x]
                )
                
                animal_row = animal_entries.iloc[selected_wl_idx]
            else:
                animal_row = animal_entries.iloc[0]
            
            # Display details
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown(f"**Age Category:** {animal_row['Age Category']}")
                st.markdown(f"**WL Reason:** {animal_row['Reason']}")
                st.markdown(f"**Highest Score:** {animal_row['Highest Score']}")
            
            with col2:
                st.markdown(f"**Entry Accuracy:** {animal_row['Entry Accuracy']}")
                st.markdown(f"**Entry Detail:** {animal_row['Entry Detail']}")
                if animal_row['Entry Temp']:
                    st.markdown(f"**Entry Temp:** {animal_row['Entry Temp']:.1f}°C")
            
            with col3:
                st.markdown(f"**Fever Sustained:** {animal_row['Fever Sustained']}")
                st.markdown(f"**Sustained Detail:** {animal_row['Sustained Detail']}")
                st.markdown(f"**Exit Accuracy:** {animal_row['Exit Accuracy']}")
            
            # Plot timeline
            fig = plot_animal_timeline(
                sensor_df,
                selected_animal,
                animal_row['Date In'],
                animal_row['Date Out'],
                animal_row['Age Category']
            )
            
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("No sensor data available for this animal in the specified time range")
        
        # Problem cases highlight
        st.header("⚠️ Problem Cases")
        
        # Only show actual problems:
        # - Invalid entry (no fever at entry)
        # - Not sustained fever (< 3 hours)
        # Note: Premature exit is actually catching animals that still have fever - this is GOOD detection
        problem_cases = filtered_df[
            (filtered_df['Entry Accuracy'] == 'Invalid') |
            (filtered_df['Fever Sustained'] == 'Not Sustained')
        ]
        
        if len(problem_cases) > 0:
            st.markdown(f"**Found {len(problem_cases)} problem cases:**")
            st.markdown("*Problem cases are WL entries with:*")
            st.markdown("- ❌ **Invalid Entry**: No fever at time of WL entry")
            st.markdown("- ❌ **Not Sustained**: Fever lasted < 3 hours")
            st.markdown("")

            problem_styled = problem_cases[['Animal ID', 'Date In', 'Reason', 
                                           'Entry Detail', 'Sustained Detail']].style.applymap(
                lambda x: 'background-color: #FADBD8',
                subset=['Entry Detail', 'Sustained Detail']
            )
            
            st.dataframe(problem_styled, use_container_width=True)
        else:
            st.success("No problem cases found in filtered results!")

else:
    st.info("👆 Please upload both Sensor Data and Watchlist Data CSV files to begin analysis")