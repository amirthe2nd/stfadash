import jdatetime
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import (
    DATA_DIR,
    calculate_difference,
    clean_measurements,
    get_auto_description,
    get_day_description,
    is_outlier,
    read_csv_with_fallback,
)


def display_month_tab(year, month, month_num, selected_equipment, cl_csv, month_csv):
    """
    Build and display the monthly tab content.
    Returns: (all_daily, UCL, LCL) or (None, None, None) if no data.
    """
    st.header("فرم ثبت و پایش پارامتر های کنترل عملیات")
    st.text(f" سال {year}٫ ماه {month}")

    if month_csv.empty:
        st.warning(f"داده‌ای برای سال {year} ماه {month} وجود ندارد.")
        return None, None, None

    if selected_equipment not in month_csv.columns:
        st.error(
            f"ستون تجهیز «{selected_equipment}» در فایل داده‌های ماهانه وجود ندارد. "
            "فایل داده باید برای هر تجهیزِ تعریف‌شده در فایل حدود کنترل، یک ستون هم‌نام داشته باشد."
        )
        st.stop()

    equipment_row = cl_csv[cl_csv["Equipment"] == selected_equipment]
    if equipment_row.empty:
        st.warning(f"هیچ حدی برای {selected_equipment} یافت نشد.")
        return None, None, None

    # Static limits from CSV
    LCL = float(equipment_row.iloc[0]["LCL"])
    UCL = float(equipment_row.iloc[0]["UCL"])
    month_csv[selected_equipment] = clean_measurements(
        month_csv[selected_equipment], UCL, LCL
    )

    # Debug info
    st.sidebar.write("--- Debug Info ---")
    st.sidebar.write(f"**UCL (static):** {UCL}")
    st.sidebar.write(f"**LCL (static):** {LCL}")
    date_col = month_csv.columns[0]
    month_csv["Jalali_Date"] = pd.to_datetime(month_csv[date_col]).dt.date.apply(
        lambda x: jdatetime.date.fromgregorian(date=x).strftime("%Y-%m-%d")
    )
    sample_avg = month_csv.groupby("Jalali_Date")[selected_equipment].mean().head(3)
    st.sidebar.write("**نمونه میانگین روزانه (۳ روز اول):**")
    st.sidebar.dataframe(sample_avg)

    st.write(f"نام تجهیز: {selected_equipment}")
    st.write(f"UCL (static): {UCL}")
    st.write(f"LCL (static): {LCL}")

    # Build daily aggregation
    all_daily = (
        month_csv.groupby("Jalali_Date")[selected_equipment].mean().reset_index()
    )
    all_daily.columns = ["Date", "Daily_Mean"]

    # Outlier flags
    all_daily["Outlier"] = (all_daily["Daily_Mean"] > UCL) | (
        all_daily["Daily_Mean"] < LCL
    )
    all_daily["Difference"] = all_daily["Daily_Mean"].apply(
        lambda x: calculate_difference(x, UCL, LCL)
    )
    all_daily["Day_Index"] = range(1, len(all_daily) + 1)

    # Monthly metrics
    monthly_sum = all_daily["Daily_Mean"].sum()
    monthly_faulty = calculate_difference(monthly_sum, UCL, LCL)
    col1, col2 = st.columns(2)
    # Monthly metrics
    if pd.isna(monthly_sum):
        col1.text("میزان انحراف ماهانه:")
        col1.error("بدون داده")
        col2.text("نتیجه ی پایش ماهانه:")
        col2.warning("داده کافی نیست")
    else:
        monthly_faulty = calculate_difference(monthly_sum, UCL, LCL)
        col1.text("میزان انحراف ماهانه:")
        if monthly_faulty == 0:
            col1.success(f"{monthly_faulty:.4f}")
        else:
            col1.error(f"{monthly_faulty:.4f}")

        if monthly_faulty == 0:
            col2.text("نتیجه ی پایش ماهانه:")
            col2.success("بدون انحراف")
        else:
            col2.text("نتیجه ی پایش ماهانه:")
            col2.error("انحراف از معیار")

    # ---------- Monthly Plot ----------
    st.write("## نمودار پایش در این دوره ی گزارش دهی")
    inside = all_daily[~all_daily["Outlier"]]
    outside = all_daily[all_daily["Outlier"]]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=all_daily["Day_Index"],
            y=all_daily["Daily_Mean"],
            mode="lines",
            name=selected_equipment,
            line=dict(color="royalblue", width=2),
            showlegend=True,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=inside["Day_Index"],
            y=inside["Daily_Mean"],
            mode="markers",
            name="در محدوده",
            marker=dict(color="blue", size=8, symbol="circle"),
            customdata=inside[["Day_Index", "Date"]].values.tolist(),
            hovertemplate=(
                f"<b>{selected_equipment}:</b> %{{y}}<br>"
                "<b>روز:</b> %{customdata[1]}<extra></extra>"
            ),
            showlegend=True,
        )
    )
    if not outside.empty:
        fig.add_trace(
            go.Scatter(
                x=outside["Day_Index"],
                y=outside["Daily_Mean"],
                mode="markers",
                name="⚠ خارج از محدوده",
                marker=dict(color="red", size=14, symbol="star"),
                customdata=outside[["Day_Index", "Date"]].values.tolist(),
                hovertemplate=(
                    f"<b>{selected_equipment}:</b> %{{y}}<br>"
                    "<b>روز:</b> %{customdata[1]}<extra></extra>"
                ),
                showlegend=True,
            )
        )
    fig.add_hline(y=UCL, line_dash="dash", line_color="red", annotation_text="UCL")
    fig.add_hline(y=LCL, line_dash="dash", line_color="red", annotation_text="LCL")
    fig.update_layout(
        title=f"میانگین روزانه - تجهیز: {selected_equipment}",
        xaxis_title="شماره روز",
        yaxis_title="مقدار میانگین روزانه",
        hovermode="x unified",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    event = st.plotly_chart(
        fig,
        use_container_width=True,
        key="monthly_plot",
        on_select="rerun",
        selection_mode="points",
    )
    if event and event.selection and event.selection.points:
        point = event.selection.points[0]
        cd = point.get("customdata")
        if cd is not None and len(cd) >= 2:
            jalali_date = cd[1]
            if jalali_date:
                st.session_state["selected_day"] = jalali_date
                st.toast(f"روز {jalali_date} انتخاب شد - به تب روزانه بروید", icon="📌")

    # ---------- Monthly Table (outlier days only) ----------
    outlier_daily = all_daily[all_daily["Outlier"]].copy()
    if "descriptions" not in st.session_state:
        st.session_state.descriptions = {}

    def _description_cache_key(date_str, equipment):
        return f"{equipment}::{date_str}"

    for idx, row in outlier_daily.iterrows():
        date_str = row["Date"]
        cache_key = _description_cache_key(date_str, selected_equipment)
        if cache_key in st.session_state.descriptions:
            continue
        day_num = int(date_str.split("-")[2])
        manual_desc = get_day_description(year, month_num, day_num)
        st.session_state.descriptions[cache_key] = manual_desc or get_auto_description(
            date_str, selected_equipment
        )

    display_data = []
    for idx, row in outlier_daily.iterrows():
        date_str = row["Date"]
        cache_key = _description_cache_key(date_str, selected_equipment)
        display_data.append(
            {
                "Date": date_str,
                selected_equipment: row["Daily_Mean"],
                "Difference": row["Difference"],
                "Description": st.session_state.descriptions.get(cache_key, ""),
            }
        )
    display_df = pd.DataFrame(display_data)

    st.write("## جدول داده های خارج از محدوده:")
    edited_df = st.data_editor(
        display_df, use_container_width=True, key="monitor_table", num_rows="dynamic"
    )

    if st.button("ذخیره توضیحات"):
        for idx, row in edited_df.iterrows():
            date_str = row["Date"]
            description = row["Description"]
            day_num = int(date_str.split("-")[2])
            day_file = DATA_DIR / str(year) / month_num / f"{day_num:02d}.csv"
            if day_file.exists():
                day_data = read_csv_with_fallback(day_file)
                day_data.columns = day_data.columns.str.strip()
                if "description" not in day_data.columns:
                    day_data["description"] = ""
                day_data["description"] = description
                day_data.to_csv(day_file, index=False)
                st.session_state.descriptions[
                    _description_cache_key(date_str, selected_equipment)
                ] = description
        st.success("✓ توضیحات ذخیره شدند")

    return all_daily, UCL, LCL
