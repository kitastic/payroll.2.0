"""Central place for paths and constants. Change these instead of hunting through code."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Point DB_DIR at your existing ../db folder to reuse master.json and the *Sales<year>.json files.
DB_DIR = BASE_DIR / "db"
MASTER_JSON = DB_DIR / "master.json"
PAYROLL_DIR = BASE_DIR / "payroll"      # exported HTML payroll + yearly <year>.xlsx 1099 book
DOWNLOAD_DIR = BASE_DIR / "tmp"         # Playwright downloads land here (one sub-folder per salon)
STATIC_DIR = BASE_DIR / "static"        # logos: ulogo.png, nlogo.png, logo.png

ZOTA_BASE = "https://pos2.zota.us"
DATE_FMT = "%m/%d/%Y"

# Selectors copied from the Selenium version. Playwright accepts xpath= directly.
SEL = {
    "username": "input[name='username']",
    "password": "input[name='password']",
    "login_btn": ".btn-login",
    "logged_in": ".avatar",
    "start_date": "input[name='startDate']",
    "end_date": "input[name='endDate']",
    "run_report": "xpath=//*[@id='root']/div/div[2]/div/main/div/div/div[2]/div[5]/button",
    "excel_link": "xpath=//div/div/div[2]/div/main/div/div/div[4]/div/div/div/div/div/div/div/div[2]/span[2]",
}

for d in (DB_DIR, PAYROLL_DIR, DOWNLOAD_DIR, STATIC_DIR):
    d.mkdir(parents=True, exist_ok=True)
