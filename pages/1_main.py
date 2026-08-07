from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from ui.month_tab import display_month_tab
BASE_DIR = Path(__file__).parent
from utils import (
    DATA_DIR,
    clean_measurements,
    get_auto_description,
    get_day_description,
    get_monthly_fault,
    is_outlier,
    normalize_control_limits,
    read_csv_with_fallback,
)

# ---------- SIDEBAR ----------
st.sidebar.header("تنظیمات")
year = st.sidebar.number_input("سال:", 1400, 1500, step=1)

month_mapping = {
    "فروردین": "01",
    "اردیبهشت": "02",
    "خرداد": "03",
    "تیر": "04",
    "مرداد": "05",
    "شهریور": "06",
    "مهر": "07",
    "آبان": "08",
    "آذر": "09",
    "دی": "10",
    "بهمن": "11",
    "اسفند": "12",
}
month = st.sidebar.selectbox("ماه:", list(month_mapping.keys()))
month_num = month_mapping[month]

# Load CL data
control_limits_path = DATA_DIR / "cl_data.csv"
if not control_limits_path.is_file():
    st.warning("ابتدا فایل حدود کنترل را از صفحهٔ بارگذاری ثبت کنید.")
    st.stop()

try:
    cl_csv = read_csv_with_fallback(control_limits_path)
except UnicodeDecodeError:
    st.error(
        "رمزگذاری فایل حدود کنترل پشتیبانی نمی‌شود. آن را با UTF-8 یا Windows-1256 ذخیره کنید."
    )
    st.stop()
cl_csv.columns = cl_csv.columns.str.strip()
if cl_csv.shape[1] < 3:
    st.error("فایل حدود کنترل باید دست‌کم سه ستون UCL، LCL و نام تجهیز داشته باشد.")
    st.stop()

cl_csv = normalize_control_limits(cl_csv)
if cl_csv.empty:
    st.error("فایل حدود کنترل معتبر نیست.")
    st.stop()
equipment_names = cl_csv["Equipment"].drop_duplicates().str.strip().tolist()
selected_equipment = st.sidebar.selectbox("نام تجهیز", equipment_names)

# ---------- TABS ----------
monthly_tab, daily_tab, yearly_tab = st.tabs(["ماهانه", "روزانه", "سالانه"])

# ---------- Global placeholders ----------
all_daily = None
UCL = None
LCL = None

# ========== MONTHLY TAB ==========
with monthly_tab:
    month_dir = DATA_DIR / str(year) / month_num
    if month_dir.exists():
        day_files = sorted(month_dir.glob("*.csv"))
        if day_files:
            dfs = []
            for day_file in day_files:
                day_df = read_csv_with_fallback(day_file)
                day_df.columns = day_df.columns.str.strip()
                dfs.append(day_df)
            month_csv = pd.concat(dfs, ignore_index=True)
            if not month_csv.empty:
                all_daily, UCL, LCL = display_month_tab(
                    year, month, month_num, selected_equipment, cl_csv, month_csv
                )
            else:
                st.warning(f"داده‌ای برای سال {year} ماه {month} وجود ندارد.")
        else:
            st.warning(f"فایلی برای سال {year} ماه {month} وجود ندارد.")
    else:
        st.warning(f"پوشهٔ ماه {month} وجود ندارد.")

# ========== DAILY TAB ==========
with daily_tab:
    daily_tab.write("### یک روز انتخاب کنید تا داده‌های آن روز را ببینید:")

    if all_daily is not None and not all_daily.empty:
        default_idx = 0
        if "selected_day" in st.session_state:
            mask = all_daily["Date"] == st.session_state["selected_day"]
            if mask.any():
                default_idx = int(all_daily[mask].index[0])

        selected_option = daily_tab.selectbox(
            "یک روز انتخاب کنید:",
            options=all_daily.index,
            format_func=lambda idx: (
                f"{all_daily.loc[idx, 'Date']} - میانگین: {all_daily.loc[idx, 'Daily_Mean']:.2f}"
            ),
            key="monitor_select",
            index=int(default_idx),
        )

        if selected_option is not None:
            selected_row = all_daily.loc[selected_option]
            selected_date = selected_row["Date"]
            day_num = int(selected_date.split("-")[2])
            manual_des = get_day_description(year, month_num, day_num)
            selected_des = manual_des or get_auto_description(
                selected_date, selected_equipment
            )

            description_cache_key = f"{selected_equipment}::{selected_date}"
            if "descriptions" not in st.session_state:
                st.session_state.descriptions = {}
            selected_description = st.session_state.descriptions.get(
                description_cache_key, selected_des
            )
            daily_tab.info(selected_description or "توضیحی برای این روز ثبت نشده است.")

            day_file = DATA_DIR / str(year) / month_num / f"{day_num:02d}.csv"

            if day_file.exists():
                day_data = read_csv_with_fallback(day_file)
                day_data.columns = day_data.columns.str.strip()
                equipment_values = (
                    clean_measurements(day_data[selected_equipment], UCL, LCL)
                    .dropna()
                    .values
                )

                col1, col2 = daily_tab.columns(2)
                with col1:
                    daily_tab.write(f"**تاریخ:** {selected_date}")
                    daily_tab.write(f"**تجهیز:** {selected_equipment}")
                    daily_tab.write(
                        f"**میانگین روزانه:** {selected_row['Daily_Mean']:.2f}"
                    )
                    daily_tab.write(f"**انحراف:** {selected_row['Difference']:.4f}")
                    daily_tab.write(f"**توضیحات:** {selected_description or 'ندارد'}")
                    description_input = daily_tab.text_input(
                        "توضیحات را اینجا وارد کنید.",
                        value=selected_description,
                        key=f"description_{year}_{month_num}_{day_num}_{selected_equipment}",
                    )
                    if daily_tab.button(
                        "ذخیره توضیحات روز",
                        key=f"save_description_{year}_{month_num}_{day_num}_{selected_equipment}",
                    ):
                        if "description" not in day_data.columns:
                            day_data["description"] = ""
                        day_data["description"] = description_input
                        day_data.to_csv(day_file, index=False)
                        st.session_state.descriptions[
                            f"{selected_equipment}::{selected_date}"
                        ] = description_input
                        daily_tab.success("توضیحات ذخیره شد")
                with col2:
                    daily_tab.write(f"**UCL:** {UCL}")
                    daily_tab.write(f"**LCL:** {LCL}")
                    daily_tab.write(
                        f"**وضعیت:** {'✅ در محدوده' if not selected_row['Outlier'] else '❌ خارج از محدوده'}"
                    )

                # Daily Plot
                def get_color(val):
                    return "red" if is_outlier(val, UCL, LCL) else "green"

                colors = [get_color(v) for v in equipment_values]

                fig_daily = go.Figure()
                fig_daily.add_trace(
                    go.Scatter(
                        x=list(range(len(equipment_values))),
                        y=equipment_values,
                        mode="lines+markers",
                        marker=dict(color=colors, size=10),
                        name=selected_equipment,
                        hovertemplate=f"<b>{selected_equipment}:</b> %{{y}}<extra></extra>",
                    )
                )
                if UCL != 0:
                    fig_daily.add_hline(
                        y=UCL, line_dash="dash", line_color="red", annotation_text="UCL"
                    )
                if LCL != 0:
                    fig_daily.add_hline(
                        y=LCL, line_dash="dash", line_color="red", annotation_text="LCL"
                    )
                fig_daily.update_layout(
                    title=f"{selected_equipment} - {selected_date}",
                    xaxis_title="شماره رکورد",
                    yaxis_title="مقدار",
                    hovermode="x unified",
                    height=500,
                    showlegend=False,
                )
                daily_tab.plotly_chart(
                    fig_daily, use_container_width=True, key="daily_chart"
                )
            else:
                daily_tab.warning("فایل روز مورد نظر وجود ندارد.")
    else:
        daily_tab.warning(
            "داده‌ای برای این ماه وجود ندارد. لطفاً ابتدا یک ماه معتبر با داده انتخاب کنید."
        )

# ========== YEARLY TAB ==========
with yearly_tab:
    col1, col2 = yearly_tab.columns(2)
    col1.write("### پایش سالانه")
    col1.text(f"سال {year}")

    monthly_results = []
    for m_num in range(1, 13):
        m_name = [name for name, num in month_mapping.items() if num == f"{m_num:02d}"]
        m_name = m_name[0] if m_name else f"{m_num:02d}"
        mean_val, fault, has_data = get_monthly_fault(
            year, f"{m_num:02d}", selected_equipment, cl_csv
        )
        if has_data and mean_val is not None:
            monthly_results.append(
                {
                    "ماه": m_name,
                    "میانگین ماهانه": mean_val,
                    "انحراف": fault if fault is not None else 0,
                    "داده موجود": True,
                }
            )
        else:
            monthly_results.append(
                {
                    "ماه": m_name,
                    "میانگین ماهانه": None,
                    "انحراف": None,
                    "داده موجود": False,
                }
            )
    df_yearly = pd.DataFrame(monthly_results)
    df_yearly = df_yearly[df_yearly["داده موجود"]]

    if not df_yearly.empty:
        avg_fault = abs(df_yearly["انحراف"].mean())
        col1.metric(
            "میانگین انحراف سالانه",
            f"{avg_fault:.4f}" if avg_fault is not None else "N/A",
        )
        col2.metric("تجهیز", selected_equipment)
        df_yearly["abs_deviation"] = df_yearly["انحراف"].abs()
        fig_yearly = px.bar(
            df_yearly,
            x="ماه",
            y="انحراف",
            title=f"انحراف ماهانه تجهیز {selected_equipment}",
            labels={
                "انحراف": "میزان انحراف",
                "ماه": "ماه",
                "abs_deviation": "انحراف مطلق",
            },
            color="abs_deviation",
            color_continuous_scale=["green", "yellow", "red"],
        )
        yearly_tab.plotly_chart(fig_yearly, use_container_width=True)
        yearly_tab.dataframe(df_yearly[["ماه", "میانگین ماهانه", "انحراف"]])
    else:
        yearly_tab.warning(f"داده‌ای برای سال {year} موجود نیست.")

    # Ranking of ALL equipment
    def compute_yearly_avg_fault(year, equipment, cl_csv, month_mapping):
        monthly_results = []
        for m_num in range(1, 13):
            m_name = [
                name for name, num in month_mapping.items() if num == f"{m_num:02d}"
            ]
            m_name = m_name[0] if m_name else f"{m_num:02d}"
            mean_val, fault, has_data = get_monthly_fault(
                year, f"{m_num:02d}", equipment, cl_csv
            )
            if has_data and mean_val is not None:
                monthly_results.append(
                    {
                        "ماه": m_name,
                        "میانگین ماهانه": mean_val,
                        "انحراف": fault if fault is not None else 0,
                        "داده موجود": True,
                    }
                )
            else:
                monthly_results.append(
                    {
                        "ماه": m_name,
                        "میانگین ماهانه": None,
                        "انحراف": None,
                        "داده موجود": False,
                    }
                )
        df_yearly = pd.DataFrame(monthly_results)
        df_yearly = df_yearly[df_yearly["داده موجود"]]
        if not df_yearly.empty:
            return abs(df_yearly["انحراف"].mean())
        return None

    equipment_names = cl_csv["Equipment"].drop_duplicates().str.strip().tolist()
    fault_dict = {}
    for equip in equipment_names:
        avg = compute_yearly_avg_fault(year, equip, cl_csv, month_mapping)
        if avg is not None:
            fault_dict[equip] = avg

    df_ranking = pd.DataFrame(
        list(fault_dict.items()), columns=["تجهیز", "میانگین انحراف سالانه"]
    )
    df_ranking = df_ranking.sort_values("میانگین انحراف سالانه", ascending=False)

    if not df_ranking.empty:
        most_faulty = df_ranking.iloc[0]
        col1, col2 = yearly_tab.columns(2)
        col2.metric("پرنقص‌ترین تجهیز", most_faulty["تجهیز"])
        col2.metric("با میانگین انحراف", most_faulty["میانگین انحراف سالانه"])
        col2.dataframe(df_ranking)
    else:
        col2.warning("هیچ داده‌ای برای هیچ تجهیزی موجود نیست.")
