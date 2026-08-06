import pandas as pd
import numpy as np
import jdatetime

def calculate_difference(value, UCL, LCL):
    """Return relative deviation if value is outside [LCL, UCL], else 0."""
    if UCL == 0 and LCL == 0:
        return 0
    if UCL != 0 and value > UCL:
        return (value - UCL) / abs(UCL)
    if LCL != 0 and value < LCL:
        return abs(LCL - value) / abs(LCL)
    return 0

def is_outlier(value, UCL, LCL):
    """Return True if value is outside the valid range."""
    if pd.isna(value):
        return False
    if UCL == 0 and LCL == 0:
        return False
    above = (value > UCL) if UCL != 0 else False
    below = (value < LCL) if LCL != 0 else False
    return above or below

def clean_measurements(values, UCL, LCL):
    """
    Convert invalid values to NaN.
    Zero is treated as missing only when zero itself is outside the control range.
    """
    cleaned = pd.to_numeric(values, errors='coerce').replace([np.inf, -np.inf], np.nan)
    if not (LCL <= 0 <= UCL):
        cleaned = cleaned.mask(cleaned == 0)
    return cleaned

def read_csv_with_fallback(path):
    """Try multiple encodings to read legacy Persian Windows CSV files."""
    last_error = None
    for encoding in ('utf-8-sig', 'cp1256', 'windows-1252', 'latin1'):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError as e:
            last_error = e
    raise last_error

def normalize_control_limits(raw_df):
    """
    Normalise the control‑limit file: expects first three columns as [UCL, LCL, Equipment].
    Splits multiple equipment names in one cell (separated by whitespace).
    """
    limits = raw_df.iloc[:, :3].copy()
    limits.columns = ['UCL', 'LCL', 'Equipment']   # note order: UCL, LCL
    limits['UCL'] = pd.to_numeric(limits['UCL'], errors='coerce')
    limits['LCL'] = pd.to_numeric(limits['LCL'], errors='coerce')
    limits['Equipment'] = limits['Equipment'].astype(str).str.strip()
    limits = limits.dropna(subset=['UCL', 'LCL', 'Equipment'])
    limits['Equipment'] = limits['Equipment'].str.split()
    return limits.explode('Equipment', ignore_index=True)

def gregorian_to_jalali_date(greg_date):
    """Convert a datetime date to Jalali string YYYY-MM-DD."""
    import jdatetime
    jd = jdatetime.date.fromgregorian(date=greg_date)
    return jd.strftime('%Y-%m-%d')
