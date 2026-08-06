import streamlit as st
from pathlib import Path

st.logo("logo.jpeg", size="large")

# Session state init
if "faulty_reasons" not in st.session_state:
    st.session_state.faulty_reasons = {}
if "selected_point" not in st.session_state:
    st.session_state.selected_point = None
if "dialog_open" not in st.session_state:
    st.session_state.dialog_open = False
if "descriptions" not in st.session_state:
    st.session_state.descriptions = {}
if "selected_day" not in st.session_state:
    st.session_state.selected_day = None

# Pages
main_page = st.Page("pages/1_main.py", title="پارامتر های کنترل عملیات", icon=":material/home:")
upload_page = st.Page("pages/4_upload.py", title="آپلود فایل")

data_dir = Path("data")
has_data = any(data_dir.glob("[0-9]*/*/*.csv"))
has_control_limits = (data_dir / "cl_data.csv").is_file()

if has_data and has_control_limits:
    menu = st.navigation({"Menu": [main_page, upload_page]})
else:
    st.info("ابتدا فایل داده و فایل حدود کنترل را بارگذاری کنید.")
    menu = st.navigation({"Menu": [upload_page]})

menu.run()
