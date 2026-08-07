import streamlit as st
import pandas as pd
from pathlib import Path
from jalaali import Jalaali
import os
import shutil
from utils import DATA_DIR

DATA_DIR.mkdir(parents=True, exist_ok=True)


def read_uploaded_csv(uploaded_file):
    """Read common UTF-8 and Persian Windows CSV encodings."""
    last_error = None
    for encoding in ("utf-8-sig", "cp1256", "windows-1252", "latin1"):
        uploaded_file.seek(0)
        try:
            return pd.read_csv(uploaded_file, encoding=encoding)
        except UnicodeDecodeError as error:
            last_error = error
    raise last_error


def gregorian_to_persian(date):
    result = Jalaali.to_jalaali(date.year, date.month, date.day)
    return result['jy'], result['jm'], result['jd']


st.write("# بارگذاری فایل ۲ ساعتی")
data_file = st.file_uploader("data", type="csv")
submit_btn = st.button("ثبت فایل")

st.divider()

st.write("# بارگذاری فایل UCL, LCL")
cl_file = st.file_uploader("cl_data", type="csv")
cl_submit_btn = st.button("ثبت فایل CL")

st.write("# بارگذاری توضیحات ")
des_file = st.file_uploader("des_data", type="csv")
des_submit_btn = st.button("ثبت فایل ")


if cl_submit_btn and cl_file is not None:
    try:
        df = read_uploaded_csv(cl_file)
    except UnicodeDecodeError:
        st.error("رمزگذاری فایل حدود کنترل پشتیبانی نمی‌شود. فایل را با UTF-8 یا Windows-1256 ذخیره کنید.")
        st.stop()
    if df.shape[1] < 3:
        st.error("فایل حدود کنترل باید دست‌کم سه ستون UCL، LCL و نام تجهیز داشته باشد.")
        st.stop()
    file_path = DATA_DIR / "cl_data.csv"
    df.to_csv(file_path, index=False, encoding="utf-8")
    st.success(f"✓ فایل ذخیره شد: {file_path}")

delete_btn = st.button("حذف داده ها", type="primary")
if delete_btn and DATA_DIR.exists():
    for item in os.listdir(DATA_DIR):
        full_path = os.path.join(DATA_DIR, item)
        if os.path.isfile(full_path) or os.path.islink(full_path):
            os.remove(full_path)
        elif os.path.isdir(full_path):
            shutil.rmtree(full_path)

if submit_btn and data_file is not None:
    try:
        df = read_uploaded_csv(data_file)
    except UnicodeDecodeError:
        st.error("رمزگذاری فایل داده پشتیبانی نمی‌شود. فایل را با UTF-8 یا Windows-1256 ذخیره کنید.")
        st.stop()

    # Remove completely empty columns
    df = df.dropna(axis=1, how='all')

    if df.empty or len(df.columns) < 2:
        st.error("فایل داده باید شامل تاریخ و حداقل یک ستون داده باشد.")
        st.stop()

    datetime_column = df.columns[0]
    try:
        df[datetime_column] = pd.to_datetime(df[datetime_column], errors='raise')
    except (TypeError, ValueError):
        st.error("ستون اول فایل داده باید شامل تاریخ معتبر باشد.")
        st.stop()

    df[['persian_year', 'persian_month', 'persian_day']] = df[datetime_column].apply(
        lambda x: pd.Series(gregorian_to_persian(x))
    )

    grouped = df.groupby(['persian_year', 'persian_month', 'persian_day'])

    file_count = 0
    for (year, month, day), group_data in grouped:
        directory = DATA_DIR / str(year) / f"{month:02d}"
        directory.mkdir(parents=True, exist_ok=True)

        # Add description column
        group_data_with_description = group_data.drop(
            columns=['persian_year', 'persian_month', 'persian_day']
        ).copy()
        group_data_with_description['description'] = ''

        file_path = directory / f"{day:02d}.csv"
        group_data_with_description.to_csv(file_path, index=False)

        st.success(f"✓ فایل ذخیره شد: {file_path}")
        file_count += 1

    st.write(f"✓ کل فایل‌های ذخیره شده: {file_count}")

if des_submit_btn and des_file is not None:
    try:
        df = read_uploaded_csv(des_file)
    except UnicodeDecodeError:
        st.error("رمزگذاری فایل حدود کنترل پشتیبانی نمی‌شود. فایل را با UTF-8 یا Windows-1256 ذخیره کنید.")
        st.stop()
    file_path = DATA_DIR / "description.csv"
    df.to_csv(file_path, index=False, encoding="utf-8")
    st.success(f"✓ فایل ذخیره شد: {file_path}")


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
_df = _load_description_csv("description.csv")
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
