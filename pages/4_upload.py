import streamlit as st
import pandas as pd
from pathlib import Path
from jalaali import Jalaali
import os
import shutil
from config import DATA_DIR
from utils import read_csv_with_fallback   # use the shared function

st.write("# بارگذاری فایل ۲ ساعتی")
data_file = st.file_uploader("data", type="csv")
submit_btn = st.button("ثبت فایل")

st.divider()

st.write("# بارگذاری فایل UCL, LCL")
cl_file = st.file_uploader("cl_data", type="csv")
cl_submit_btn = st.button("ثبت فایل CL")

if cl_submit_btn and cl_file is not None:
    try:
        df = read_csv_with_fallback(cl_file)   # using shared function
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
if delete_btn:
    for item in DATA_DIR.iterdir():
        if item.is_file() or item.is_symlink():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)

if submit_btn and data_file is not None:
    try:
        df = read_csv_with_fallback(data_file)   # shared function
    except UnicodeDecodeError:
        st.error("رمزگذاری فایل داده پشتیبانی نمی‌شود. فایل را با UTF-8 یا Windows-1256 ذخیره کنید.")
        st.stop()
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
    def gregorian_to_persian(date):
        result = Jalaali.to_jalaali(date.year, date.month, date.day)
        return result['jy'], result['jm'], result['jd']
    df[['persian_year', 'persian_month', 'persian_day']] = df[datetime_column].apply(
        lambda x: pd.Series(gregorian_to_persian(x))
    )
    grouped = df.groupby(['persian_year', 'persian_month', 'persian_day'])
    file_count = 0
    for (year, month, day), group_data in grouped:
        directory = DATA_DIR / str(year) / f"{month:02d}"
        directory.mkdir(parents=True, exist_ok=True)
        group_data_with_description = group_data.drop(
            columns=['persian_year', 'persian_month', 'persian_day']
        ).copy()
        group_data_with_description['description'] = ''
        file_path = directory / f"{day:02d}.csv"
        group_data_with_description.to_csv(file_path, index=False)
        st.success(f"✓ فایل ذخیره شد: {file_path}")
        file_count += 1
    st.write(f"✓ کل فایل‌های ذخیره شده: {file_count}")
