"""
Entry point.   python main.py
Layers:
    views/        NiceGUI widgets. Only talk to the controller.
    controllers/  AppController (the old Ai). Coordinates models + services.
    models/       Salon, Employee*. Pure data and payroll math.
    services/     Playwright scraper, Excel parser, JSON repo, exporter.
"""
import logging
import os

from nicegui import app, ui

import config
from controllers.app_controller import AppController
from views import main_view
from views.state import ViewState
from views.widgets import UiLogHandler

log_handler = UiLogHandler()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("payroll").addHandler(log_handler)

# HEADLESS=0 python main.py   -> watch the browser while it scrapes (handy when Zota changes its page)
# controller = AppController(headless=os.getenv("HEADLESS", "1") != "0")
controller = AppController(headless=os.getenv("HEADLESS", "0") != "0")

app.add_static_files("/static", config.STATIC_DIR)
app.add_static_files("/payroll", config.PAYROLL_DIR)


@ui.page("/")
def index():
    state = ViewState(controller)
    main_view.build(state, log_handler)


native = os.getenv("NATIVE", "0") == "1"      # NATIVE=1 opens a desktop window (needs pywebview)
ui.run(
    title="KP Payroll",
    port=8090,
    reload=False,
    dark=True,
    native=native,
    window_size=(1400, 950) if native else None,
)
