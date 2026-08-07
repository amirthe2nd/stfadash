from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

# ---------- Base path ----------
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"


# ---------- Description CSV loading ----------
def _load_description_csv(filename):
    path = DATA_DIR / filename
    for encoding in ("utf-8-sig", "cp1256", "windows-1252", "latin1"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    return pd.DataFrame()


def _normalize_jalali_date(value):
    parts = str(value).strip().split("/")
    if len(parts) != 3:
        return str(value).strip()
    try:
        y, m, d = parts
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    except ValueError:
        return str(value).strip()


_description_frames = []
for filename in ("description2.csv", "description.csv"):
    _df = _load_description_csv(filename)
    if not _df.empty:
        _df.columns = _df.columns.str.strip()
        _description_frames.append(_df)

if _description_frames:
    description_csv = pd.concat(_description_frames, ignore_index=True)
    description_csv.iloc[:, 0] = description_csv.iloc[:, 0].apply(
        _normalize_jalali_date
    )
else:
    description_csv = pd.DataFrame()

DESCRIPTION_COLUMN_BY_PREFIX = {"B1": 1, "B2": 3}
DEFAULT_DESCRIPTION_COLUMN = 5


def get_description_column(equipment_tag):
    tag = str(equipment_tag).upper()
    for prefix, col in DESCRIPTION_COLUMN_BY_PREFIX.items():
        if tag.startswith(prefix):
            return col
    return DEFAULT_DESCRIPTION_COLUMN


def get_auto_description(jalali_date_str, equipment_tag):
    if description_csv.empty:
        return ""
    match = description_csv[description_csv.iloc[:, 0] == str(jalali_date_str)]
    if match.empty:
        return ""
    col = get_description_column(equipment_tag)
    value = str(match.iloc[0, col]).strip()
    if value in ("", "/", "nan"):
        return ""
    return value


# ---------- Core helper functions ----------
def calculate_difference(value, UCL, LCL):
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
    raise last_error


def normalize_control_limits(raw_df):
    limits = raw_df.iloc[:, :3].copy()
    limits.columns = ["LCL", "UCL", "Equipment"]
    limits["LCL"] = pd.to_numeric(limits["LCL"], errors="coerce")
    limits["UCL"] = pd.to_numeric(limits["UCL"], errors="coerce")
    limits["Equipment"] = limits["Equipment"].astype(str).str.strip()
    limits = limits.dropna(subset=["LCL", "UCL", "Equipment"])
    limits["Equipment"] = limits["Equipment"].str.split()
    return limits.explode("Equipment", ignore_index=True)


def get_monthly_fault(year, month_num, equipment, cl_df):
    month_dir = DATA_DIR / str(year) / month_num
    if not month_dir.exists():
        return None, None, False
    day_files = sorted(month_dir.glob("*.csv"))
    if not day_files:
        return None, None, False
    dfs = []
    for day_file in day_files:
        day_df = pd.read_csv(day_file)
        day_df.columns = day_df.columns.str.strip()
        dfs.append(day_df)
    month_csv = pd.concat(dfs, ignore_index=True)
    if month_csv.empty or equipment not in month_csv.columns:
        return None, None, False
    eq_row = cl_df[cl_df.iloc[:, 2] == equipment]
    if eq_row.empty:
        return pd.to_numeric(month_csv[equipment], errors="coerce").mean(), None, True
    UCL = float(eq_row.iloc[0, 0])
    LCL = float(eq_row.iloc[0, 1])
    monthly_mean = clean_measurements(month_csv[equipment], UCL, LCL).mean()
    fault = calculate_difference(monthly_mean, UCL, LCL)
    return monthly_mean, fault, True
