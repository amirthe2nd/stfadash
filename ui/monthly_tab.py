import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
from config import DATA_DIR
from utils import is_outlier, calculate_difference  # keep your existing imports

def render_monthly_tab(year, month, month_num, equipment, daily_df, UCL, LCL, cl_df):
    """
    Draw the complete monthly tab.
    daily_df must contain columns: Date, Daily_Mean, Outlier, Difference, Day_Index.
    """
    st.header("فرم ثبت و پایش پارامتر های کنترل عملیات")
    st.text(f" سال {year}٫ ماه {month}")

    if daily_df.empty:
        st.header(f"فایلی برای سال {year} ماه {month} وجود ندارد.")
        return

    # ---------- Ensure UCL and LCL are valid numeric scalars ----------
    try:
        UCL = float(UCL)
        LCL = float(LCL)
    except (TypeError, ValueError):
        st.error("محدودیت‌های کنترلی (UCL/LCL) معتبر نیستند. لطفاً فایل کنترل را بررسی کنید.")
        return

    # Show equipment info
    st.write(f"نام تجهیز: {equipment}")
    st.write(f"UCL: {UCL:.4f}")
    st.write(f"LCL: {LCL:.4f}")

    col1, col2 = st.columns(2)

    monthly_mean = daily_df['Daily_Mean'].mean()
    monthly_faulty = calculate_difference(monthly_mean, UCL, LCL)

    with col1:
        st.text("میزان انحراف ماهانه:")
        if monthly_faulty != 0:
            st.error(f"{monthly_faulty:.4f}")
        else:
            st.error("N/A")
    with col2:
        st.text("نتیجه ی پایش ماهانه:")
        if monthly_faulty == 0:
            st.success("بدون انحراف")
        else:
            st.error("انحراف از معیار")

    # ---------- Monthly Plot (FIXED) ----------
    st.write("## نمودار پایش در این دوره ی گزارش دهی")

    # ---- Work on a copy ----
    all_daily = daily_df.copy()

    # ---- Outlier detection (vectorised, no apply) ----
    
    all_daily['Outlier'] = (all_daily['Daily_Mean'] > UCL) | (all_daily['Daily_Mean'] < LCL)

    mean_y = all_daily['Daily_Mean'].mean()
    std_y = all_daily['Daily_Mean'].std()
    UCL = mean_y + 3 * std_y
    LCL = mean_y - 3 * std_y

    # ---- 2. Force‑recompute the Outlier flag (ignore any existing column) ----
    all_daily['Outlier'] = (all_daily['Daily_Mean'] > UCL) | (all_daily['Daily_Mean'] < LCL)
    
    # ---- 3. Debug info (remove after confirming it works) ----
    num_outliers = all_daily['Outlier'].sum()
    st.info(f"تعداد نقاط خارج از محدوده: {num_outliers} از {len(all_daily)}")
                
    
    inside = all_daily[~all_daily['Outlier']]
    outside = all_daily[all_daily['Outlier']]

    # Debug info (remove or comment after verifying)
    st.info(f"تعداد نقاط خارج از محدوده: {len(outside)} از {len(all_daily)}")

    fig = go.Figure()

    # Main line
    fig.add_trace(go.Scatter(
        x=all_daily['Day_Index'],
        y=all_daily['Daily_Mean'],
        mode='lines',
        name=equipment,
        line=dict(color='royalblue', width=2)
        showlegend=True
    ))
    
    # Inside points (blue circles)
    fig.add_trace(go.Scatter(
        x=inside['Day_Index'],
        y=inside['Daily_Mean'],
        mode='markers',
        name='در محدوده',
        marker=dict(color='blue', size=8, symbol='circle'),
        customdata=inside[['Day_Index', 'Date']].values.tolist(),
        hovertemplate=(f"<b>{equipment}:</b> %{{y}}<br><b>روز:</b> %{{customdata[1]}}<extra></extra>"),
        showlegend=True
    ))
    # Outside points (red stars)
    if not outside.empty:
        fig.add_trace(go.Scatter(
            x=outside['Day_Index'],
            y=outside['Daily_Mean'],
            mode='markers',
            name='⚠ خارج از محدوده',
            marker=dict(color='red', size=14, symbol='star'),
            customdata=outside[['Day_Index', 'Date']].values.tolist(),
            hovertemplate=(f"<b>{equipment}:</b> %{{y}}<br><b>روز:</b> %{{customdata[1]}}<extra></extra>"),
            showlegend=True
        ))
    # Control limits
    fig.add_hline(y=UCL, line_dash="dash", line_color="red", annotation_text="UCL")
    fig.add_hline(y=LCL, line_dash="dash", line_color="red", annotation_text="LCL")
    
    fig.update_layout(
        title=f"میانگین روزانه - تجهیز: {equipment}",
        xaxis_title="شماره روز",
        yaxis_title="مقدار میانگین روزانه",
        hovermode='x unified',
        template='plotly_white',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

     event = monthly_tab.plotly_chart(
                        fig,
                        use_container_width=True,
                        key="monthly_plot",
                        on_select="rerun",
                        selection_mode="points"
                    )
    if event and event.selection and event.selection.points:
        point = event.selection.points[0]
        cd = point.get('customdata')
        if cd is not None and len(cd) >= 2:
            jalali_date = cd[1]
            if jalali_date:
                st.session_state['selected_day'] = jalali_date
                st.toast(f"روز {jalali_date} انتخاب شد - به تب روزانه بروید", icon="📌")

    # ---------- Table of outlier days ----------
    outlier_daily = all_daily[all_daily['Outlier']].copy()

    # Load descriptions from CSV files (only for outlier days)
    if 'descriptions' not in st.session_state:
        st.session_state.descriptions = {}
    for date_str in outlier_daily['Date']:
        if date_str not in st.session_state.descriptions:
            day_num = int(date_str.split('-')[2])
            day_file = DATA_DIR / str(year) / month_num / f"{day_num:02d}.csv"
            if day_file.exists():
                day_data = pd.read_csv(day_file)
                day_data.columns = day_data.columns.str.strip()
                if 'description' in day_data.columns:
                    desc = day_data['description'].dropna().astype(str)
                    desc = desc[desc.str.strip() != '']
                    if not desc.empty:
                        st.session_state.descriptions[date_str] = desc.iloc[0]

    display_data = []
    for _, row in outlier_daily.iterrows():
        date_str = row['Date']
        display_data.append({
            'Date': date_str,
            equipment: row['Daily_Mean'],
            'Difference': row['Difference'],
            'Description': st.session_state.descriptions.get(date_str, '')
        })
    display_df = pd.DataFrame(display_data)

    st.write("## جدول داده های خارج از محدوده:")
    edited_df = st.data_editor(display_df, use_container_width=True,
                               key="monitor_table", num_rows="dynamic")

    if st.button("ذخیره توضیحات"):
        for _, row in edited_df.iterrows():
            date_str = row['Date']
            description = row['Description']
            day_num = int(date_str.split('-')[2])
            day_file = DATA_DIR / str(year) / month_num / f"{day_num:02d}.csv"
            if day_file.exists():
                day_data = pd.read_csv(day_file)
                day_data.columns = day_data.columns.str.strip()
                if 'description' not in day_data.columns:
                    day_data['description'] = ''
                day_data['description'] = description
                day_data.to_csv(day_file, index=False)
                st.session_state.descriptions[date_str] = description
        st.success("✓ توضیحات ذخیره شدند")
