import streamlit as st
import pandas as pd
from pathlib import Path
from config import DATA_DIR, CONTROL_LIMITS_PATH
from utils import (
    read_csv_with_fallback,
    normalize_control_limits,
    gregorian_to_jalali_date,
    clean_measurements,
    is_outlier,
    calculate_difference
)

@st.cache_data
def load_control_limits():
    """Load and normalise the control‑limits file once per session."""
    if not CONTROL_LIMITS_PATH.is_file():
        return pd.DataFrame()
    df = read_csv_with_fallback(CONTROL_LIMITS_PATH)
    df.columns = df.columns.str.strip()
    if df.shape[1] < 3:
        raise ValueError("Control limits file must have at least three columns.")
    cl_df = normalize_control_limits(df)
    return cl_df

@st.cache_data
def load_month_data(year, month_num):
    """
    Load all daily CSV files for a given (year, month) into one DataFrame.
    Returns empty DataFrame if directory does not exist or no files.
    """
    month_dir = DATA_DIR / str(year) / month_num
    if not month_dir.exists():
        return pd.DataFrame()
    day_files = sorted(month_dir.glob('*.csv'))
    if not day_files:
        return pd.DataFrame()
    dfs = []
    for day_file in day_files:
        day_df = pd.read_csv(day_file)
        day_df.columns = day_df.columns.str.strip()
        dfs.append(day_df)
    return pd.concat(dfs, ignore_index=True)

def prepare_month_data(month_df, equipment, UCL, LCL):
    """
    Clean the equipment column, compute daily averages, add outlier flags.
    Returns a DataFrame with columns: Date, Daily_Mean, Outlier, Difference, Day_Index.
    """
    if month_df.empty or equipment not in month_df.columns:
        return pd.DataFrame()
    # Clean the equipment column
    month_df[equipment] = clean_measurements(month_df[equipment], UCL, LCL)
    # Convert first column to Jalali date
    date_col = month_df.columns[0]
    month_df['Jalali_Date'] = pd.to_datetime(month_df[date_col]).dt.date.apply(gregorian_to_jalali_date)
    # Daily averages
    daily = month_df.groupby('Jalali_Date')[equipment].mean().reset_index()
    daily.columns = ['Date', 'Daily_Mean']
    daily['Outlier'] = daily['Daily_Mean'].apply(lambda x: is_outlier(x, UCL, LCL))
    daily['Difference'] = daily['Daily_Mean'].apply(lambda x: calculate_difference(x, UCL, LCL))
    daily['Day_Index'] = range(1, len(daily) + 1)
    return daily
