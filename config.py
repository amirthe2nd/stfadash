from pathlib import Path

# ---------- Paths ----------
DATA_DIR = Path("data")
CONTROL_LIMITS_PATH = DATA_DIR / "cl_data.csv"

# ---------- Month mapping (Persian to numeric) ----------
MONTH_MAPPING = {
    'فروردین': '01', 'اردیبهشت': '02', 'خرداد': '03', 'تیر': '04',
    'مرداد': '05', 'شهریور': '06', 'مهر': '07', 'آبان': '08',
    'آذر': '09', 'دی': '10', 'بهمن': '11', 'اسفند': '12'
}
