import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
from config import DATA_DIR
from utils import is_outlier, clean_measurements

def render_daily_tab(year, month_num, equipment, daily_df, UCL, LCL):
    """
    Render the daily tab. Uses st.session_state['selected_day'] to pre‑select a day.
    """
    st.write("### یک روز انتخاب کنید تا داده‌های آن روز را ببینید:")

    if daily_df.empty:
        st.warning("داده‌ای برای این ماه وجود ندارد.")
        return

    # Determine default index
    default_idx = 0
    if 'selected_day' in st.session_state:
        mask = daily_df['Date'] == st.session_state['selected_day']
        if mask.any():
            default_idx = int(daily_df[mask].index[0])

    selected_option = st.selectbox(
        "یک روز انتخاب کنید:",
        options=daily_df.index,
        format_func=lambda idx: f"{daily_df.loc[idx, 'Date']} - میانگین: {daily_df.loc[idx, 'Daily_Mean']:.2f}",
        key="monitor_select",
        index=int(default_idx)
    )

    if selected_option is None:
        return

    selected_row = daily_df.loc[selected_option]
    selected_date = selected_row['Date']
    selected_description = st.session_state.descriptions.get(selected_date, '')

    day_num = int(selected_date.split('-')[2])
    day_file = DATA_DIR / str(year) / month_num / f"{day_num:02d}.csv"
    if not day_file.exists():
        st.warning("فایل روز مورد نظر یافت نشد.")
        return

    day_data = pd.read_csv(day_file)
    day_data.columns = day_data.columns.str.strip()
    equipment_values = clean_measurements(day_data[equipment], UCL, LCL).dropna().values

    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**تاریخ:** {selected_date}")
        st.write(f"**تجهیز:** {equipment}")
        st.write(f"**میانگین روزانه:** {selected_row['Daily_Mean']:.2f}")
        st.write(f"**انحراف:** {selected_row['Difference']:.4f}")
        st.write(f"**توضیحات:** {selected_description or 'ندارد'}")
        description_input = st.text_input(
            "توضیحات را اینجا وارد کنید.",
            value=selected_description,
            key=f"description_{year}_{month_num}_{day_num}"
        )
    with col2:
        st.write(f"**UCL:** {UCL}")
        st.write(f"**LCL:** {LCL}")
        st.write(f"**وضعیت:** {'✅ در محدوده' if not selected_row['Outlier'] else '❌ خارج از محدوده'}")

    # Daily scatter plot
    colors = ['red' if is_outlier(v, UCL, LCL) else 'green' for v in equipment_values]
    fig_daily = go.Figure()
    fig_daily.add_trace(go.Scatter(
        x=list(range(len(equipment_values))),
        y=equipment_values,
        mode='lines+markers',
        marker=dict(color=colors, size=10),
        name=equipment,
        hovertemplate=f"<b>{equipment}:</b> %{{y}}<extra></extra>"
    ))
    if UCL != 0:
        fig_daily.add_hline(y=UCL, line_dash="dash", line_color="red", annotation_text="UCL")
    if LCL != 0:
        fig_daily.add_hline(y=LCL, line_dash="dash", line_color="red", annotation_text="LCL")
    fig_daily.update_layout(
        title=f"{equipment} - {selected_date}",
        xaxis_title="شماره رکورد",
        yaxis_title="مقدار",
        hovermode='x unified',
        height=500,
        showlegend=False
    )
    st.plotly_chart(fig_daily, use_container_width=True, key="daily_chart")

    if st.button("ذخیره توضیحات روز", key=f"save_description_{year}_{month_num}_{day_num}"):
        if 'description' not in day_data.columns:
            day_data['description'] = ''
        day_data['description'] = description_input
        day_data.to_csv(day_file, index=False)
        st.session_state.descriptions[selected_date] = description_input
        st.success("توضیحات ذخیره شد")
