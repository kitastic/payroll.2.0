# KP Payroll — NiceGUI + Playwright

A rewrite of the PySimpleGUI + Selenium payroll app. It keeps the same screens, the same payroll math, and the same data files.

## Setup (Windows)

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium        :: once — replaces the chromedriver download hack
```

Point it at your existing data. In `config.py`, set `DB_DIR` to the folder that holds `master.json` and `upscaleSales2026.json` etc. Or copy those files into `./db/`. Drop `logo.png`, `ulogo.png` and `nlogo.png` into `./static/`.

```bat
python main.py                 :: opens http://localhost:8090 in your browser
set NATIVE=1 && python main.py :: desktop window instead (pip install pywebview)
set HEADLESS=0 && python main.py :: watch Chromium while it scrapes Zota
```

## Structure (old → new)

| Old | New | Role |
|---|---|---|
| `View.py` (one big event loop) | `views/main_view.py`, `employees_tab.py`, `salon_tab.py`, `reports_tab.py`, `log_tab.py` | UI only; each button calls the controller directly |
| `Ai.py` | `controllers/app_controller.py` | The only thing views talk to |
| `Salon.py` (inherited `Bot`) | `models/salon.py` | Data + payroll orchestration, no browser, no popups |
| `Employee.py` | `models/employee.py` | Same math; `make_employee()` picks the class |
| `Bot.py` + `helper.py` (Selenium) | `services/zota_scraper.py` | Async Playwright |
| `Salon.readSalesXltoJson` | `services/sales_parser.py` | Excel → dict |
| JSON code spread over Salon/Ai | `services/sales_repo.py` | Read/merge/query the yearly JSON files |
| `Salon.exportPayroll` | `services/exporter.py` | HTML slips + `<year>.xlsx` 1099 rows |

Models never import NiceGUI. When something needs the user (e.g. an employee found in sales but missing from settings), the model returns it in `PayrollResult.unknown_employees` and the view asks.

## Playwright notes

* Locators wait on their own, so `waitLoadingClick` / `waitLoadingPresence` are gone.
* `page.expect_download()` returns the file directly. No more polling the folder for `.crdownload` or renaming the newest file.
* The arrow-key date entry is kept because Zota's masked input goes blank if you clear it.
* Selectors live in `config.SEL`. If Zota changes its page, fix them there. Run with `HEADLESS=0` to watch.
* Ranges over 180 days are split into chunks automatically (your old `splitRange`).

## Bugs fixed along the way

* `Employee.getStatus` read a `'totalsale'` key that never existed, so View Status always failed.
* `Salon.getPayroll` returned 2 values on error, but `Ai` unpacked 3, which crashed.
* Role checks mixed `'Janitor'` / `'janitor'` / `'checkdeal'` casing; they are case-insensitive now.
* Export crashed with an `IndexError` when no one had sales. Now it shows a message.
* `helper.waitLoading*` caught Python's `TimeoutError` instead of Selenium's `TimeoutException`.
* Saving settings now writes `master.json.bak` first.

## Security

Zota passwords sit in plain text in `master.json` (and were hardcoded in the old `app.py`). Keep `db/` out of git (see `.gitignore`). Change the password if those files were ever shared.
