import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import jdatetime
import os

# ---------- Helper Functions ----------
def calculate_difference(value, UCL, LCL):
    """Return the relative deviation if value is outside [LCL, UCL], else 0.
       Handles zero limits gracefully.
    """
    if UCL == 0 and LCL == 0:
        return 0
    # Check upper side
    if UCL != 0 and value > UCL:
        return (value - UCL) / abs(UCL)
    # Check lower side
    if LCL != 0 and value < LCL:
        return abs(LCL - value) / abs(LCL)
    return 0

def is_outlier(value, UCL, LCL):
    """Return True if value is outside the valid range, handling zero limits."""
    if pd.isna(value):
        return False
    if UCL == 0 and LCL == 0:
        return False
    above = (value > UCL) if UCL != 0 else False
    below = (value < LCL) if LCL != 0 else False
    return above or below

def clean_measurements(values, UCL, LCL):
    """Convert invalid values to NaN before calculating means.

    A zero reading is treated as missing only when zero itself is outside the
    configured control range; this avoids false alarms from offline sensors.
    """
    cleaned = pd.to_numeric(values, errors='coerce').replace([np.inf, -np.inf], np.nan)
    if not (LCL <= 0 <= UCL):
        cleaned = cleaned.mask(cleaned == 0)
    return cleaned

def read_csv_with_fallback(path):
    """Support legacy Persian Windows-encoded control-limit files."""
    last_error = None
    for encoding in ('utf-8-sig', 'cp1256', 'windows-1252', 'latin1'):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError as error:
            last_error = error
    raise last_error

def normalize_control_limits(raw_df):
    """Normalize this project's LCL, UCL, tag control-limit export."""
    limits = raw_df.iloc[:, :3].copy()
    limits.columns = ['LCL', 'UCL', 'Equipment']
    limits['LCL'] = pd.to_numeric(limits['LCL'], errors='coerce')
    limits['UCL'] = pd.to_numeric(limits['UCL'], errors='coerce')
    limits['Equipment'] = limits['Equipment'].astype(str).str.strip()
    limits = limits.dropna(subset=['LCL', 'UCL', 'Equipment'])

    # Some exports put several whitespace-separated equipment tags in one cell.
    # Give each tag the same control limits so it matches the data-file columns.
    limits['Equipment'] = limits['Equipment'].str.split()
    return limits.explode('Equipment', ignore_index=True)

def get_monthly_fault(year, month_num, equipment, cl_df):
    """Compute monthly mean and fault value for a given equipment."""
    month_dir = Path(f'data/{year}/{month_num}')
    if not month_dir.exists():
        return None, None, False
    day_files = sorted(month_dir.glob('*.csv'))
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
        return pd.to_numeric(month_csv[equipment], errors='coerce').mean(), None, True
    UCL = float(eq_row.iloc[0, 0])
    LCL = float(eq_row.iloc[0, 1])
    monthly_mean = clean_measurements(month_csv[equipment], UCL, LCL).mean()
    fault = calculate_difference(monthly_mean, UCL, LCL)
    return monthly_mean, fault, True

# ---------- SIDEBAR ----------
st.sidebar.header("تنظیمات")
year = st.sidebar.number_input("سال:", 1400, 1500, step=1)

month_mapping = {
    'فروردین': '01', 'اردیبهشت': '02', 'خرداد': '03', 'تیر': '04',
    'مرداد': '05', 'شهریور': '06', 'مهر': '07', 'آبان': '08',
    'آذر': '09', 'دی': '10', 'بهمن': '11', 'اسفند': '12'
}
month = st.sidebar.selectbox('ماه:', list(month_mapping.keys()))
month_num = month_mapping[month]

# Load CL data
control_limits_path = Path('data/cl_data.csv')
if not control_limits_path.is_file():
    st.warning("ابتدا فایل حدود کنترل را از صفحهٔ بارگذاری ثبت کنید.")
    st.stop()

try:
    cl_csv = read_csv_with_fallback(control_limits_path)
except UnicodeDecodeError:
    st.error("رمزگذاری فایل حدود کنترل پشتیبانی نمی‌شود. آن را با UTF-8 یا Windows-1256 ذخیره کنید.")
    st.stop()
cl_csv.columns = cl_csv.columns.str.strip()
if cl_csv.shape[1] < 3:
    st.error("فایل حدود کنترل باید دست‌کم سه ستون UCL، LCL و نام تجهیز داشته باشد.")
    st.stop()

cl_csv = normalize_control_limits(cl_csv)
if cl_csv.empty:
    st.error("فایل حدود کنترل معتبر نیست.")
    st.stop()
equipment_names = cl_csv.iloc[:, 2].str.strip().tolist()
selected_equipment = st.sidebar.selectbox("نام تجهیز", equipment_names)

# ---------- TABS ----------
monthly_tab, daily_tab, yearly_tab = st.tabs(["ماهانه", "روزانه", "سالانه"])

# ========== MONTHLY TAB ==========
monthly_tab.header("فرم ثبت و پایش پارامتر های کنترل عملیات")
monthly_tab.text(f" سال {year}٫ ماه {month}")

month_dir = Path(f'data/{year}/{month_num}')
if month_dir.exists():
    day_files = sorted(month_dir.glob('*.csv'))
    if not day_files:
        monthly_tab.header(f"فایلی برای سال {year} ماه {month} وجود ندارد.")
    else:
        dfs = []
        for day_file in day_files:
            day_df = pd.read_csv(day_file)
            day_df.columns = day_df.columns.str.strip()
            dfs.append(day_df)
        month_csv = pd.concat(dfs, ignore_index=True)

        if month_csv.empty:
            monthly_tab.header(f"فایلی برای سال {year} ماه {month} وجود ندارد.")
        else:
            if selected_equipment not in month_csv.columns:
                monthly_tab.error(
                    f"ستون تجهیز «{selected_equipment}» در فایل داده‌های ماهانه وجود ندارد. "
                    "فایل داده باید برای هر تجهیزِ تعریف‌شده در فایل حدود کنترل، یک ستون هم‌نام داشته باشد."
                )
                st.stop()

            equipment_row = cl_csv[cl_csv.iloc[:, 2] == selected_equipment]
            if not equipment_row.empty:
                UCL = float(equipment_row.iloc[0, 0])
                LCL = float(equipment_row.iloc[0, 1])
                month_csv[selected_equipment] = clean_measurements(
                    month_csv[selected_equipment], UCL, LCL
                )

                # ===== Debug info (shown in sidebar) =====
                st.sidebar.write("--- Debug Info ---")
                st.sidebar.write(f"**UCL:** {UCL}")
                st.sidebar.write(f"**LCL:** {LCL}")
                # Compute daily averages to show sample
                date_col = month_csv.columns[0]
                month_csv['Jalali_Date'] = pd.to_datetime(month_csv[date_col]).dt.date.apply(
                    lambda x: jdatetime.date.fromgregorian(date=x).strftime('%Y-%m-%d')
                )
                sample_avg = month_csv.groupby('Jalali_Date')[selected_equipment].mean().head(3)
                st.sidebar.write("**نمونه میانگین روزانه (۳ روز اول):**")
                st.sidebar.dataframe(sample_avg)
                # ========================================

                monthly_tab.write(f"نام تجهیز: {selected_equipment}")
                monthly_tab.write(f"UCL: {UCL}")
                monthly_tab.write(f"LCL: {LCL}")
                col1, col2 = monthly_tab.columns(2)

                monthly_mean = month_csv[selected_equipment].mean()
                monthly_faulty = calculate_difference(monthly_mean, UCL, LCL)

                if monthly_faulty != 0:
                    col1.text("میزان انحراف ماهانه:")
                    col1.error(f"{monthly_faulty:.4f}")
                else:
                    col1.text("میزان انحراف ماهانه:")
                    col1.error("N/A")

                if monthly_faulty == 0:
                    col2.text("نتیجه ی پایش ماهانه:")
                    col2.success("بدون انحراف")
                else:
                    col2.text("نتیجه ی پایش ماهانه:")
                    col2.error("انحراف از معیار")

                # ---------- Build full daily aggregation ----------
                all_daily = month_csv.groupby('Jalali_Date')[selected_equipment].mean().reset_index()
                all_daily.columns = ['Date', 'Daily_Mean']

                # ---- Outlier detection using the new function ----
                all_daily['Outlier'] = all_daily['Daily_Mean'].apply(lambda x: is_outlier(x, UCL, LCL))
                all_daily['Difference'] = all_daily['Daily_Mean'].apply(lambda x: calculate_difference(x, UCL, LCL))
                all_daily['Day_Index'] = range(1, len(all_daily) + 1)

                # ---------- Monthly Plot ----------
                monthly_tab.write("## نمودار پایش در این دوره ی گزارش دهی")
                
                # ---- 1. Ensure UCL and LCL are defined ----
                # (If you already have them from elsewhere, skip these two lines)
                mean_y = all_daily['Daily_Mean'].mean()
                std_y = all_daily['Daily_Mean'].std()
                UCL = mean_y + 3 * std_y
                LCL = mean_y - 3 * std_y
                
                # ---- 2. Force‑recompute the Outlier flag (ignore any existing column) ----
                all_daily['Outlier'] = (all_daily['Daily_Mean'] > UCL) | (all_daily['Daily_Mean'] < LCL)
                
                # ---- 3. Debug info (remove after confirming it works) ----
                num_outliers = all_daily['Outlier'].sum()
                st.info(f"تعداد نقاط خارج از محدوده: {num_outliers} از {len(all_daily)}")
                
                # ---- 4. Split data ----
                inside = all_daily[~all_daily['Outlier']]
                outside = all_daily[all_daily['Outlier']]
                
                # ---- 5. Build figure ----
                fig = go.Figure()
                
                # Main line (all points, line only)
                fig.add_trace(go.Scatter(
                    x=all_daily['Day_Index'],
                    y=all_daily['Daily_Mean'],
                    mode='lines',
                    name=selected_equipment,
                    line=dict(color='royalblue', width=2),
                    showlegend=True
                ))

                # Blue dots for points INSIDE
                fig.add_trace(go.Scatter(
                    x=inside['Day_Index'],
                    y=inside['Daily_Mean'],
                    mode='markers',
                    name='در محدوده',
                    marker=dict(color='blue', size=8, symbol='circle'),
                    customdata=inside[['Day_Index', 'Date']].values.tolist(),
                    hovertemplate=(
                        f"<b>{selected_equipment}:</b> %{{y}}<br>"
                        "<b>روز:</b> %{customdata[1]}<extra></extra>"
                    ),
                    showlegend=True
                ))
                
                # Red stars for points OUTSIDE
                if not outside.empty:
                    fig.add_trace(go.Scatter(
                        x=outside['Day_Index'],
                        y=outside['Daily_Mean'],
                        mode='markers',
                        name='⚠ خارج از محدوده',
                        marker=dict(color='red', size=14, symbol='star'),
                        customdata=outside[['Day_Index', 'Date']].values.tolist(),
                        hovertemplate=(
                            f"<b>{selected_equipment}:</b> %{{y}}<br>"
                            "<b>روز:</b> %{customdata[1]}<extra></extra>"
                        ),
                        showlegend=True
                    ))

                    # Control limits (always drawn)
                    fig.add_hline(y=UCL, line_dash="dash", line_color="red", annotation_text="UCL")
                    fig.add_hline(y=LCL, line_dash="dash", line_color="red", annotation_text="LCL")
                    
                    # Layout
                    fig.update_layout(
                        title=f"میانگین روزانه - تجهیز: {selected_equipment}",
                        xaxis_title="شماره روز",
                        yaxis_title="مقدار میانگین روزانه",
                        hovermode='x unified',
                        template='plotly_white',
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1
                        )
                    )
                    
                    # ---- 6. Display plot and handle click ----
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
                            jalali_date = cd[1]   # 'Date' column contains the Jalali string
                            if jalali_date:
                                st.session_state['selected_day'] = jalali_date
                                st.toast(f"روز {jalali_date} انتخاب شد - به تب روزانه بروید", icon="📌")
                                
                    
                # ---------- Monthly Table (outlier days only) ----------
                outlier_daily = all_daily[all_daily['Outlier']].copy()

                if 'descriptions' not in st.session_state:
                    st.session_state.descriptions = {}
                    for idx, row in outlier_daily.iterrows():
                        date_str = row['Date']
                        day_num = int(date_str.split('-')[2])
                        day_file = Path(f'data/{year}/{month_num}/{day_num:02d}.csv')
                        if day_file.exists():
                            day_data = pd.read_csv(day_file)
                            day_data.columns = day_data.columns.str.strip()
                            if 'description' in day_data.columns:
                                desc = day_data['description'].dropna().astype(str)
                                desc = desc[desc.str.strip() != '']
                                if not desc.empty:
                                    st.session_state.descriptions[date_str] = desc.iloc[0]

                display_data = []
                for idx, row in outlier_daily.iterrows():
                    date_str = row['Date']
                    display_data.append({
                        'Date': date_str,
                        selected_equipment: row['Daily_Mean'],
                        'Difference': row['Difference'],
                        'Description': st.session_state.descriptions.get(date_str, '')
                    })
                display_df = pd.DataFrame(display_data)
                
                monthly_tab.write("## جدول داده های خارج از محدوده:")
                edited_df = monthly_tab.data_editor(
                    display_df,
                    use_container_width=True,
                    key="monitor_table",
                    num_rows="dynamic"
                )
                
                if monthly_tab.button("ذخیره توضیحات"):
                    for idx, row in edited_df.iterrows():
                        date_str = row['Date']
                        description = row['Description']
                        day_num = int(date_str.split('-')[2])
                        day_file = Path(f'data/{year}/{month_num}/{day_num:02d}.csv')
                        if day_file.exists():
                            day_data = pd.read_csv(day_file)
                            day_data.columns = day_data.columns.str.strip()
                            if 'description' not in day_data.columns:
                                day_data['description'] = ''
                            day_data['description'] = description
                            day_data.to_csv(day_file, index=False)
                            st.session_state.descriptions[date_str] = description
                    monthly_tab.success("✓ توضیحات ذخیره شدند")

                # ========== DAILY TAB ==========
                daily_tab.write("### یک روز انتخاب کنید تا داده‌های آن روز را ببینید:")

                if not all_daily.empty:
                    default_idx = 0
                    if 'selected_day' in st.session_state:
                        mask = all_daily['Date'] == st.session_state['selected_day']
                        if mask.any():
                            default_idx = int(all_daily[mask].index[0])

                    selected_option = daily_tab.selectbox(
                        "یک روز انتخاب کنید:",
                        options=all_daily.index,
                        format_func=lambda idx: f"{all_daily.loc[idx, 'Date']} - میانگین: {all_daily.loc[idx, 'Daily_Mean']:.2f}",
                        key="monitor_select",
                        index=int(default_idx)
                    )

                    if selected_option is not None:
                        selected_row = all_daily.loc[selected_option]
                        selected_date = selected_row['Date']
                        selected_description = st.session_state.descriptions.get(selected_date, '')

                        day_num = int(selected_date.split('-')[2])
                        day_file = Path(f'data/{year}/{month_num}/{day_num:02d}.csv')

                        if day_file.exists():
                            day_data = pd.read_csv(day_file)
                            day_data.columns = day_data.columns.str.strip()
                            equipment_values = clean_measurements(
                                day_data[selected_equipment], UCL, LCL
                            ).dropna().values

                            
                            col1, col2 = daily_tab.columns(2)
                            with col1:
                                daily_tab.write(f"**تاریخ:** {selected_date}")
                                daily_tab.write(f"**تجهیز:** {selected_equipment}")
                                daily_tab.write(f"**میانگین روزانه:** {selected_row['Daily_Mean']:.2f}")
                                daily_tab.write(f"**انحراف:** {selected_row['Difference']:.4f}")
                                daily_tab.write(f"**توضیحات:** {selected_description or 'ندارد'}")
                                description_input = daily_tab.text_input(
                                    "توضیحات را اینجا وارد کنید.",
                                    value=selected_description,
                                    key=f"description_{year}_{month_num}_{day_num}"
                                )
                            with col2:
                                daily_tab.write(f"**UCL:** {UCL}")
                                daily_tab.write(f"**LCL:** {LCL}")
                                daily_tab.write(f"**وضعیت:** {'✅ در محدوده' if not selected_row['Outlier'] else '❌ خارج از محدوده'}")

                            # Daily Plot (Scatter)
                        def get_color(val):
                            return 'red' if is_outlier(val, UCL, LCL) else 'green'
                        
                        colors = [get_color(v) for v in equipment_values]

                        fig_daily = go.Figure()
                        fig_daily.add_trace(go.Scatter(
                            x=list(range(len(equipment_values))),
                            y=equipment_values,
                            mode='lines+markers',
                            marker=dict(color=colors, size=10),
                            name=selected_equipment,
                            hovertemplate=f"<b>{selected_equipment}:</b> %{{y}}<extra></extra>"
                        ))
                        if UCL != 0:
                            fig_daily.add_hline(y=UCL, line_dash="dash", line_color="red", annotation_text="UCL")
                        if LCL != 0:
                            fig_daily.add_hline(y=LCL, line_dash="dash", line_color="red", annotation_text="LCL")
                        fig_daily.update_layout(
                            title=f"{selected_equipment} - {selected_date}",
                            xaxis_title="شماره رکورد",
                            yaxis_title="مقدار",
                            hovermode='x unified',
                            height=500,
                            showlegend=False
                        )
                        daily_tab.plotly_chart(fig_daily, use_container_width=True, key="daily_chart")
                        if daily_tab.button("ذخیره توضیحات روز", key=f"save_description_{year}_{month_num}_{day_num}"):
                            if 'description' not in day_data.columns:
                                day_data['description'] = ''
                            day_data['description'] = description_input
                            day_data.to_csv(day_file, index=False)
                            st.session_state.descriptions[selected_date] = description_input
                            daily_tab.success("توضیحات ذخیره شد")
                else:
                    daily_tab.warning("داده‌ای برای این ماه وجود ندارد.")

            else:
                monthly_tab.warning(f"هیج حدی برای {selected_equipment} یافت نشد.")
else:
    monthly_tab.header(f"فایلی برای سال {year} ماه {month} وجود ندارد.")


# ========== YEARLY TAB ==========
col1, col2 = yearly_tab.columns(2)
col1.write("### پایش سالانه")
col1.text(f"سال {year}")

monthly_results = []
for m_num in range(1, 13):
    m_name = [name for name, num in month_mapping.items() if num == f"{m_num:02d}"]
    m_name = m_name[0] if m_name else f"{m_num:02d}"
    mean_val, fault, has_data = get_monthly_fault(year, f"{m_num:02d}", selected_equipment, cl_csv)
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
yearly_max = df_yearly.max()
col2.write("### بیشترین انحراف در سال بر حسب تجهیز")
col2.text(yearly_max['ماه'])
col2.text(yearly_max['انحراف'])

if not df_yearly.empty:
    avg_fault = abs(df_yearly['انحراف'].mean())
    yearly_tab.metric("میانگین انحراف سالانه", f"{avg_fault:.4f}" if avg_fault is not None else "N/A")

    df_yearly['abs_deviation'] = df_yearly['انحراف'].abs()

    fig_yearly = px.bar(
        df_yearly,
        x='ماه',
        y='انحراف',
        title=f"انحراف ماهانه تجهیز {selected_equipment}",
        labels={'انحراف': 'میزان انحراف', 'ماه': 'ماه', 'abs_deviation': 'انحراف مطلق'},
        color='abs_deviation',   
        color_continuous_scale=['green', 'yellow', 'red'],  
    )
    yearly_tab.plotly_chart(fig_yearly, use_container_width=True)
    yearly_tab.dataframe(df_yearly[['ماه', 'میانگین ماهانه', 'انحراف']])
else:
    yearly_tab.warning(f"داده‌ای برای سال {year} موجود نیست.")
