import glob
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
    compute_equipment_faults,
    get_auto_description,
    get_day_description,
    get_monthly_fault,
    is_outlier,
    load_yearly_data,
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

    # 1. Load all data for the year (ONCE)
    yearly_df = load_yearly_data(year)

    if yearly_df.empty:
        yearly_tab.warning(f"داده‌ای برای سال {year} موجود نیست.")
    else:
        # 2. Overall equipment ranking
        all_equip_faults = compute_equipment_faults(yearly_df)  # returns all equipment
        if not all_equip_faults.empty:
            # Sort descending (most faulty first)
            equip_ranking = all_equip_faults.sort_values(
                "AvgDeviation", ascending=False
            )
            equip_ranking.columns = ["تجهیز", "میانگین انحراف سالانه"]

            avg_fault_overall = equip_ranking["میانگین انحراف سالانه"].mean()
            col1.metric(
                "میانگین انحراف سالانه (کل تجهیزات)",
                f"{avg_fault_overall:.4f}" if pd.notna(avg_fault_overall) else "N/A",
            )
            col2.metric("تجهیز انتخاب شده", selected_equipment)

            # Display ranking in an expander
            with yearly_tab.expander("رتبه‌بندی تجهیزات بر اساس انحراف"):
                yearly_tab.dataframe(equip_ranking)
                if not equip_ranking.empty:
                    fig_rank = px.bar(
                        equip_ranking.head(10),
                        x="تجهیز",
                        y="میانگین انحراف سالانه",
                        title="ده تجهیز با بیشترین انحراف سالانه",
                    )
                    yearly_tab.plotly_chart(fig_rank, use_container_width=True)
        else:
            yearly_tab.warning("هیچ داده‌ای برای محاسبه انحراف تجهیزات موجود نیست.")

        # 3. Monthly deviation chart for the selected equipment
        if selected_equipment:
            if selected_equipment in yearly_df.columns:
                # Compute monthly average value and deviation from yearly average
                equip_series = yearly_df[selected_equipment]
                monthly_avg = (
                    yearly_df.groupby("month")[selected_equipment].mean().reset_index()
                )
                yearly_avg = equip_series.mean()
                monthly_avg["deviation"] = abs(
                    monthly_avg[selected_equipment] - yearly_avg
                )

                # Map month number to Persian month name
                monthly_avg["month_name"] = monthly_avg["month"].apply(
                    lambda m: (
                        [
                            name
                            for name, num in month_mapping.items()
                            if num == f"{m:02d}"
                        ][0]
                        if any
                        else f"{m:02d}"
                    )
                )

                # Plot monthly deviation
                fig_yearly = px.bar(
                    monthly_avg,
                    x="month_name",
                    y="deviation",
                    title=f"انحراف ماهانه تجهیز {selected_equipment}",
                    labels={"deviation": "میزان انحراف", "month_name": "ماه"},
                    color="deviation",
                    color_continuous_scale=["green", "yellow", "red"],
                )
                yearly_tab.plotly_chart(fig_yearly, use_container_width=True)

                # Display monthly table
                monthly_display = monthly_avg[
                    ["month_name", selected_equipment, "deviation"]
                ]
                monthly_display.columns = ["ماه", "میانگین ماهانه", "انحراف"]
                yearly_tab.dataframe(monthly_display)
            else:
                yearly_tab.warning(
                    f"تجهیز {selected_equipment} در داده‌های سال {year} یافت نشد."
                )

        # 4. MOST FAULTY EQUIPMENT (since each column is one "signal")
        if not all_equip_faults.empty:
            worst = all_equip_faults.loc[all_equip_faults["AvgDeviation"].idxmax()]
            worst_equip = worst["Equipment"]
            worst_val = worst["AvgDeviation"]

            yearly_tab.write("### بیشترین تجهیز پرنقص")
            col1, col2 = yearly_tab.columns(2)
            col1.metric("پرنقص‌ترین تجهیز", worst_equip)
            col1.metric("میانگین انحراف", f"{worst_val:.4f}")

            # Also show a bar chart of all equipment deviations
            fig_sig = px.bar(
                all_equip_faults.sort_values("AvgDeviation", ascending=False),
                x="Equipment",
                y="AvgDeviation",
                title="میانگین انحراف سالانه تمام تجهیزات",
                labels={"AvgDeviation": "میانگین انحراف", "Equipment": "تجهیز"},
                color="AvgDeviation",
                color_continuous_scale=["green", "yellow", "red"],
            )
            yearly_tab.plotly_chart(fig_sig, use_container_width=True)
            yearly_tab.dataframe(
                all_equip_faults.sort_values("AvgDeviation", ascending=False)
            )
        else:
            yearly_tab.warning("داده‌ای برای محاسبه انحراف تجهیزات موجود نیست.")

        # ========== NEW: MOST DEVIATION FROM CONTROL LIMITS ==========
        yearly_tab.write("### بیشترین انحراف از حدود کنترل")
        # Get UCL and LCL for selected equipment from cl_csv
        ucl_row = cl_csv[cl_csv["Equipment"].str.strip() == selected_equipment]
        if not ucl_row.empty:
            UCL = ucl_row["UCL"].values[0]
            LCL = ucl_row["LCL"].values[0]
            # Check if selected equipment exists in yearly data
            if selected_equipment in yearly_df.columns:
                # Compute daily means
                daily_means = (
                    yearly_df.groupby("date")[selected_equipment].mean().reset_index()
                )
                daily_means.rename(
                    columns={selected_equipment: "daily_mean"}, inplace=True
                )

                # Compute deviation: positive if outside limits, else 0
                daily_means["deviation"] = daily_means["daily_mean"].apply(
                    lambda x: max(0, x - UCL, LCL - x)
                )

                # Find the day with maximum deviation
                max_dev_row = daily_means.loc[daily_means["deviation"].idxmax()]
                worst_date = max_dev_row["date"]
                worst_dev = max_dev_row["deviation"]
                worst_mean = max_dev_row["daily_mean"]

                # Display metrics
                col1, col2 = yearly_tab.columns(2)
                col1.metric("تاریخ پرانحراف‌ترین روز", worst_date)
                col1.metric("میانگین روزانه", f"{worst_mean:.4f}")
                col2.metric("انحراف از حدود", f"{worst_dev:.4f}")
                col2.metric("وضعیت", "خارج از محدوده" if worst_dev > 0 else "در محدوده")

                # Plot daily means with UCL/LCL and highlight the worst day
                import plotly.graph_objects as go

                fig_limits = go.Figure()
                fig_limits.add_trace(
                    go.Scatter(
                        x=daily_means["date"],
                        y=daily_means["daily_mean"],
                        mode="lines+markers",
                        name="میانگین روزانه",
                        marker=dict(color="blue"),
                    )
                )
                fig_limits.add_hline(
                    y=UCL, line_dash="dash", line_color="red", annotation_text="UCL"
                )
                fig_limits.add_hline(
                    y=LCL, line_dash="dash", line_color="red", annotation_text="LCL"
                )
                # Highlight the worst point
                fig_limits.add_trace(
                    go.Scatter(
                        x=[worst_date],
                        y=[worst_mean],
                        mode="markers",
                        marker=dict(color="red", size=14, symbol="star"),
                        name="بیشترین انحراف",
                    )
                )
                fig_limits.update_layout(
                    title=f"میانگین روزانه {selected_equipment} با حدود کنترل",
                    xaxis_title="تاریخ",
                    yaxis_title="مقدار",
                    hovermode="x unified",
                    height=500,
                )
                yearly_tab.plotly_chart(fig_limits, use_container_width=True)

                # Optionally show a table of all days with deviation
                with yearly_tab.expander("نمایش جدول تمام روزها"):
                    yearly_tab.dataframe(
                        daily_means.sort_values("deviation", ascending=False)
                    )
            else:
                yearly_tab.warning(
                    f"تجهیز {selected_equipment} در داده‌های سال {year} یافت نشد."
                )
        else:
            yearly_tab.warning(
                f"حدود کنترل برای تجهیز {selected_equipment} در فایل cl_data.csv یافت نشد."
            )
