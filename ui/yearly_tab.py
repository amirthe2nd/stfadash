import streamlit as st
import pandas as pd
import plotly.express as px
from config import MONTH_MAPPING
from data_loader import load_month_data
from utils import clean_measurements, calculate_difference

def get_monthly_fault(year, month_num, equipment, cl_df):
    """
    Compute monthly mean and fault for a given equipment.
    Returns (mean, fault, has_data).
    """
    month_df = load_month_data(year, month_num)
    if month_df.empty or equipment not in month_df.columns:
        return None, None, False

    eq_row = cl_df[cl_df['Equipment'] == equipment]
    if eq_row.empty:
        mean_val = pd.to_numeric(month_df[equipment], errors='coerce').mean()
        return mean_val, None, True

    UCL = float(eq_row.iloc[0]['UCL'])
    LCL = float(eq_row.iloc[0]['LCL'])
    cleaned = clean_measurements(month_df[equipment], UCL, LCL)
    monthly_mean = cleaned.mean()
    fault = calculate_difference(monthly_mean, UCL, LCL)
    return monthly_mean, fault, True

def render_yearly_tab(year, equipment, cl_df):
    st.write("### پایش سالانه")
    st.text(f"سال {year}")

    monthly_results = []
    for m_num in range(1, 13):
        m_name = [name for name, num in MONTH_MAPPING.items() if num == f"{m_num:02d}"]
        m_name = m_name[0] if m_name else f"{m_num:02d}"
        mean_val, fault, has_data = get_monthly_fault(year, f"{m_num:02d}", equipment, cl_df)
        if has_data and mean_val is not None:
            monthly_results.append({
                'ماه': m_name,
                'میانگین ماهانه': mean_val,
                'انحراف': fault if fault is not None else 0,
                'داده موجود': True
            })
        else:
            monthly_results.append({
                'ماه': m_name,
                'میانگین ماهانه': None,
                'انحراف': None,
                'داده موجود': False
            })

    df_yearly = pd.DataFrame(monthly_results)
    df_yearly = df_yearly[df_yearly['داده موجود']]

    if not df_yearly.empty:
        yearly_max = df_yearly.max()
        col1, col2 = st.columns(2)
        with col1:
            st.metric("بیشترین انحراف در سال", f"{yearly_max['انحراف']:.4f}")   # or use text
            st.write(f"ماه: {yearly_max['ماه']}")
        avg_fault = abs(df_yearly['انحراف'].mean())
        st.metric("میانگین انحراف سالانه", f"{avg_fault:.4f}")

        df_yearly['abs_deviation'] = df_yearly['انحراف'].abs()
        fig = px.bar(
            df_yearly,
            x='ماه',
            y='انحراف',
            title=f"انحراف ماهانه تجهیز {equipment}",
            labels={'انحراف': 'میزان انحراف', 'ماه': 'ماه', 'abs_deviation': 'انحراف مطلق'},
            color='abs_deviation',
            color_continuous_scale=['green', 'yellow', 'red'],
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df_yearly[['ماه', 'میانگین ماهانه', 'انحراف']])
    else:
        st.warning(f"داده‌ای برای سال {year} موجود نیست.")
