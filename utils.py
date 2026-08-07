import glob
import os
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

# ---------- Base path ----------
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"


# ---------- Description CSV loading ----------
DESCRIPTION_FILES = ("description2.csv", "description.csv")
DESCRIPTION_COLUMN_BY_PREFIX = {"B1": 1, "B2": 3}
DEFAULT_DESCRIPTION_COLUMN = 5


def load_yearly_data(year):
    """
    Load all day CSV files for a given year.
    Assumes:
      - Folder: data/{year}/{month:02d}/
      - Each CSV: first column is a date (ignored), remaining columns are equipment names.
      - Filename is day number (e.g., 01.csv)
    Returns DataFrame with columns: date (YYYY-MM-DD), month (int), and equipment columns.
    """
    all_dfs = []
    for month in range(1, 13):
        month_str = f"{month:02d}"
        path = f"data/{year}/{month_str}/*.csv"
        for file in glob.glob(path):
            day_num = int(os.path.basename(file).split(".")[0])
            df = pd.read_csv(file)
            # Drop the first column (assumed date) – we'll use our own date
            if len(df.columns) > 0:
                df.drop(df.columns[0], axis=1, inplace=True)
            df["date"] = f"{year}-{month_str}-{day_num:02d}"
            df["month"] = month
            all_dfs.append(df)
    if not all_dfs:
        return pd.DataFrame()
    return pd.concat(all_dfs, ignore_index=True)


def compute_equipment_faults(yearly_df, equipment=None):
    """
    For each equipment column (all columns except the first 'date' and 'month'),
    compute the average absolute deviation from the monthly median.

    Parameters:
        yearly_df : wide DataFrame (columns: date, month, Equipment1, Equipment2, ...)
        equipment  : (optional) if provided, return fault for that single equipment

    Returns:
        DataFrame with columns: Equipment, AvgDeviation
    """
    if yearly_df.empty:
        return pd.DataFrame()

    # Identify equipment columns: all columns except 'date' and 'month'
    # The first column is date – we can detect it as the only non-numeric? Or we can assume we drop it.
    # Better: we drop columns that are definitely not equipment: 'date' and 'month'
    cols_to_drop = ["month"]
    # The date column might have any name, so we drop any column that is not numeric?
    # We'll assume the first column is date; we'll drop it by position.
    # Since we added 'month', we can safely drop the first column (position 0) if it's the date.
    # But to be safe, we can identify columns that are not equipment by checking if they are not numeric.
    # Actually, we can keep all columns except 'month' and the date column.
    # We'll assume the date column is the first column in the original CSV.
    # We'll drop it by checking if it's the only non-numeric column besides 'month'?
    # Simpler: we'll drop any column that is of object type or is named 'date' or similar.
    # Let's just drop columns that are not numeric (since equipment values should be numeric).
    numeric_cols = yearly_df.select_dtypes(include=["number"]).columns.tolist()
    # Exclude 'month' from numeric_cols if it's there (it is numeric)
    equipment_cols = [col for col in numeric_cols if col != "month"]
    if not equipment_cols:
        return pd.DataFrame()

    # Filter by equipment if specified
    if equipment is not None:
        if equipment not in equipment_cols:
            return pd.DataFrame()
        equipment_cols = [equipment]

    # We'll melt the equipment columns into long format
    df_melted = yearly_df.melt(
        id_vars=["month"],
        value_vars=equipment_cols,
        var_name="Equipment",
        value_name="Value",
    )

    # Compute monthly median per equipment
    monthly_baseline = (
        df_melted.groupby(["Equipment", "month"])["Value"]
        .median()
        .reset_index()
        .rename(columns={"Value": "Baseline"})
    )

    # Merge baseline and compute absolute deviation
    df_with_baseline = df_melted.merge(monthly_baseline, on=["Equipment", "month"])
    df_with_baseline["Deviation"] = abs(
        df_with_baseline["Value"] - df_with_baseline["Baseline"]
    )

    # Average deviation per equipment over the year
    yearly_fault = (
        df_with_baseline.groupby("Equipment")["Deviation"]
        .mean()
        .reset_index()
        .rename(columns={"Deviation": "AvgDeviation"})
    )
    return yearly_fault


def _load_description_csv(filename):
    """Load one optional description CSV using the same encoding fallback as the app."""
    path = DATA_DIR / filename
    if not path.is_file():
        return pd.DataFrame()

    for encoding in ("utf-8-sig", "cp1256", "windows-1252", "latin1"):
        try:
            df = pd.read_csv(path, encoding=encoding)
            df.columns = df.columns.astype(str).str.strip()
            return df
        except UnicodeDecodeError:
            continue
    return pd.DataFrame()


def _normalize_jalali_date(value):
    """Normalize Jalali dates such as 1404/01/02 to 1404-01-02."""
    parts = str(value).strip().split("/")
    if len(parts) != 3:
        return str(value).strip()
    try:
        y, m, d = parts
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    except ValueError:
        return str(value).strip()


def load_description_data():
    """Load the current description files when an automatic description is requested."""
    frames = []

    for filename in DESCRIPTION_FILES:
        df = _load_description_csv(filename)
        if not df.empty and df.shape[1] >= 1:
            df.iloc[:, 0] = df.iloc[:, 0].apply(_normalize_jalali_date)
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


def get_description_column(equipment_tag):
    tag = str(equipment_tag).upper()
    for prefix, col in DESCRIPTION_COLUMN_BY_PREFIX.items():
        if tag.startswith(prefix):
            return col
    return DEFAULT_DESCRIPTION_COLUMN


def get_auto_description(jalali_date_str, equipment_tag):
    """Return the automatic description for a date/equipment, or an empty string."""
    description_csv = load_description_data()

    if description_csv.empty or description_csv.shape[1] < 1:
        return ""

    match = description_csv[
        description_csv.iloc[:, 0] == _normalize_jalali_date(jalali_date_str)
    ]
    if match.empty:
        return ""

    col = get_description_column(equipment_tag)
    if col >= match.shape[1]:
        return ""

    value = str(match.iloc[0, col]).strip()
    if value.lower() in ("", "/", "nan", "none"):
        return ""
    return value


def get_day_description(year, month_num, day_num):
    """Read a manually saved description from a daily data CSV."""
    day_file = DATA_DIR / str(year) / str(month_num) / f"{int(day_num):02d}.csv"
    if not day_file.is_file():
        return ""

    try:
        day_data = read_csv_with_fallback(day_file)
    except (UnicodeDecodeError, pd.errors.ParserError, OSError):
        return ""

    day_data.columns = day_data.columns.astype(str).str.strip()
    if "description" not in day_data.columns:
        return ""

    descriptions = day_data["description"].dropna().astype(str)
    descriptions = descriptions[descriptions.str.strip() != ""]
    return descriptions.iloc[0].strip() if not descriptions.empty else ""


# ---------- Core helper functions ----------
def calculate_difference(value, UCL, LCL):
    if pd.isna(value):
        return 0
    if UCL == 0 and LCL == 0:
        return 0
    if UCL != 0 and value > UCL:
        return (value - UCL) / abs(UCL)
    if LCL != 0 and value < LCL:
        return abs(LCL - value) / abs(LCL)
    return 0


def is_outlier(value, UCL, LCL):
    if pd.isna(value):
        return False
    if UCL == 0 and LCL == 0:
        return False
    above = (value > UCL) if UCL != 0 else False
    below = (value < LCL) if LCL != 0 else False
    return above or below


def clean_measurements(values, UCL, LCL):
    cleaned = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if not (LCL <= 0 <= UCL):
        cleaned = cleaned.mask(cleaned == 0)
    return cleaned


def read_csv_with_fallback(path):
    last_error = None
    for encoding in ("utf-8-sig", "cp1256", "windows-1252", "latin1"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError as error:
            last_error = error
    if last_error is not None:
        raise last_error
    return pd.read_csv(path)


def normalize_control_limits(raw_df):
    if raw_df is None or raw_df.shape[1] < 3:
        return pd.DataFrame(columns=["LCL", "UCL", "Equipment"])

    limits = raw_df.iloc[:, :3].copy()
    limits.columns = ["LCL", "UCL", "Equipment"]
    limits["LCL"] = pd.to_numeric(limits["LCL"], errors="coerce")
    limits["UCL"] = pd.to_numeric(limits["UCL"], errors="coerce")
    limits["Equipment"] = limits["Equipment"].astype(str).str.strip()

    limits = limits.dropna(subset=["LCL", "UCL", "Equipment"])
    limits = limits[limits["Equipment"] != ""]

    # One row may contain multiple equipment names separated by spaces.
    limits["Equipment"] = limits["Equipment"].str.split()
    limits = limits.explode("Equipment", ignore_index=True)
    return limits


def get_monthly_fault(year, month_num, equipment, cl_df):
    month_dir = DATA_DIR / str(year) / str(month_num)
    if not month_dir.exists():
        return None, None, False

    day_files = sorted(month_dir.glob("*.csv"))
    if not day_files:
        return None, None, False

    dfs = []
    for day_file in day_files:
        try:
            day_df = read_csv_with_fallback(day_file)
        except (UnicodeDecodeError, pd.errors.ParserError, OSError):
            continue
        day_df.columns = day_df.columns.astype(str).str.strip()
        dfs.append(day_df)

    if not dfs:
        return None, None, False

    month_csv = pd.concat(dfs, ignore_index=True)
    if month_csv.empty or equipment not in month_csv.columns:
        return None, None, False

    eq_row = cl_df[cl_df["Equipment"] == equipment]
    if eq_row.empty:
        return (
            pd.to_numeric(month_csv[equipment], errors="coerce").mean(),
            None,
            True,
        )

    # normalize_control_limits guarantees the named order LCL/UCL/Equipment.
    LCL = float(eq_row.iloc[0]["LCL"])
    UCL = float(eq_row.iloc[0]["UCL"])

    monthly_mean = clean_measurements(month_csv[equipment], UCL, LCL).mean()
    fault = calculate_difference(monthly_mean, UCL, LCL)
    return monthly_mean, fault, True
