import streamlit as st
import pandas as pd
from pathlib import Path
from config import MONTH_MAPPING, DATA_DIR
from data_loader import load_control_limits, load_month_data, prepare_month_data
from ui.monthly_tab import render_monthly_tab
from ui.daily_tab import render_daily_tab
from ui.yearly_tab import render_yearly_tab

# ---------- SIDEBAR ----------
st.sidebar.header("تنظیمات")
year = st.sidebar.number_input("سال:", 1400, 1500, step=1)
month = st.sidebar.selectbox('ماه:', list(MONTH_MAPPING.keys()))
month_num = MONTH_MAPPING[month]

# Load control limits (cached)
cl_df = load_control_limits()
if cl_df.empty:
    st.warning("ابتدا فایل حدود کنترل را از صفحهٔ بارگذاری ثبت کنید.")
    st.stop()

equipment_names = cl_df['Equipment'].str.strip().tolist()
selected_equipment = st.sidebar.selectbox("نام تجهیز", equipment_names)

# Get control limits for this equipment
eq_row = cl_df[cl_df['Equipment'] == selected_equipment]
if eq_row.empty:
    st.error(f"هیچ حدی برای {selected_equipment} یافت نشد.")
    st.stop()
UCL = float(eq_row.iloc[0]['UCL'])
LCL = float(eq_row.iloc[0]['LCL'])

# Load month data (cached)
month_df = load_month_data(year, month_num)
if not month_df.empty and selected_equipment not in month_df.columns:
    st.error(
        f"ستون تجهیز «{selected_equipment}» در فایل داده‌های ماهانه وجود ندارد. "
        "فایل داده باید برای هر تجهیزِ تعریف‌شده در فایل حدود کنترل، یک ستون هم‌نام داشته باشد."
    )
    st.stop()

# Prepare daily aggregates (this is not cached because it depends on UCL/LCL and cleaning)
if not month_df.empty:
    daily_df = prepare_month_data(month_df, selected_equipment, UCL, LCL)
else:
    daily_df = pd.DataFrame()

# ----- Debug info (optional) – placed AFTER daily_df is defined -----
st.sidebar.write("--- Debug Info ---")
st.sidebar.write(f"UCL: {UCL}, LCL: {LCL}")
if not daily_df.empty:
    st.sidebar.write(f"تعداد روزها: {len(daily_df)}")
    st.sidebar.write(f"میانگین کلی: {daily_df['Daily_Mean'].mean():.2f}")
    st.sidebar.write(f"نمونه‌ای از میانگین‌های روزانه:\n{daily_df['Daily_Mean'].head()}")
# ------------------------------------------------------------------

# Store in session_state for use across tabs (optional but avoids recomputation)
st.session_state['daily_df'] = daily_df
st.session_state['UCL'] = UCL
st.session_state['LCL'] = LCL
st.session_state['selected_equipment'] = selected_equipment
st.session_state['year'] = year
st.session_state['month_num'] = month_num

# ---------- TABS ----------
monthly_tab, daily_tab, yearly_tab = st.tabs(["ماهانه", "روزانه", "سالانه"])

with monthly_tab:
    render_monthly_tab(year, month, month_num, selected_equipment, daily_df, UCL, LCL, cl_df)

with daily_tab:
    render_daily_tab(year, month_num, selected_equipment, daily_df, UCL, LCL)

with yearly_tab:
    render_yearly_tab(year, selected_equipment, cl_df)
