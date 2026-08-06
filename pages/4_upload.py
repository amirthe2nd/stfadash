import streamlit as st
import pandas as pd
from pathlib import Path
from jalaali import Jalaali
import os
import shutil


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


st.write("# بارگذاری فایل ۲ ساعتی")
data_file = st.file_uploader("data", type="csv")
submit_btn = st.button("ثبت فایل")

st.divider()

st.write("# بارگذاری فایل UCL, LCL")
cl_file = st.file_uploader("cl_data", type="csv")
cl_submit_btn = st.button("ثبت فایل CL")

if cl_submit_btn and cl_file is not None:
    try:
        df = read_uploaded_csv(cl_file)
    except UnicodeDecodeError:
        st.error("رمزگذاری فایل حدود کنترل پشتیبانی نمی‌شود. فایل را با UTF-8 یا Windows-1256 ذخیره کنید.")
        st.stop()
    if df.shape[1] < 3:
        st.error("فایل حدود کنترل باید دست‌کم سه ستون UCL، LCL و نام تجهیز داشته باشد.")
        st.stop()
    file_path = os.path.join("data/", "cl_data.csv")
    df.to_csv(file_path, index=False, encoding="utf-8")
    st.success(f"✓ فایل ذخیره شد: {file_path}")

delete_btn = st.button("حذف داده ها", type="primary")
if delete_btn == True:
    for item in os.listdir("data"):
        full_path = os.path.join("data", item)
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
    
    def gregorian_to_persian(date):
        result = Jalaali.to_jalaali(date.year, date.month, date.day)
        return result['jy'], result['jm'], result['jd']
    
    df[['persian_year', 'persian_month', 'persian_day']] = df[datetime_column].apply(
        lambda x: pd.Series(gregorian_to_persian(x))
    )
    
    grouped = df.groupby(['persian_year', 'persian_month', 'persian_day'])
    
    file_count = 0
    for (year, month, day), group_data in grouped:
        directory = f"data/{year}/{month:02d}"
        Path(directory).mkdir(parents=True, exist_ok=True)
        
        # Add description column
        group_data_with_description = group_data.drop(
            columns=['persian_year', 'persian_month', 'persian_day']
        ).copy()
        group_data_with_description['description'] = ''
        
        file_path = f"{directory}/{day:02d}.csv"
        group_data_with_description.to_csv(file_path, index=False)
        
        st.success(f"✓ فایل ذخیره شد: {file_path}")
        file_count += 1
    
    st.write(f"✓ کل فایل‌های ذخیره شده: {file_count}")
    
