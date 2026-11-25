"""
Top-level page: menu bar, header toolbar, tabs, bottom notice bar.
Equivalent of View.__setup__ + openApp, but each tab lives in its own module and
every button calls the controller directly (no big if/elif event loop).
"""
from __future__ import annotations

import datetime as dt
import logging
import tempfile
from pathlib import Path

from nicegui import app, ui

import config
from controllers.app_controller import week_of
from views import employees_tab, log_tab, reports_tab, salon_tab
from views.state import ViewState
from views.widgets import UiLogHandler, date_input, icon_button, mono

log = logging.getLogger("payroll")


async def read_upload(e) -> tuple[str, bytes]:
    """Works with NiceGUI 2.x (e.content) and 3.x (e.file)."""
    if hasattr(e, "file"):
        return e.file.name, await e.file.read()
    return e.name, e.content.read()


def build(state: ViewState, log_handler: UiLogHandler) -> None:
    ctrl = state.ctrl
    ui.dark_mode(True)
    ui.colors(primary="#4a90d9")

    # ================================================================ shared actions
    def salons_menu(container, action, prefix: str = ""):
        """(Re)fills a dropdown with 'All' + active salons (old bm1/bm2 ButtonMenu)."""
        container.clear()
        with container:
            for name in ["All", *ctrl.salon_names()]:
                ui.item(prefix + name.capitalize(), on_click=lambda n=name: action(n))

    def refresh_last_dates():
        reg, mod = ctrl.latest_dates("regular"), ctrl.latest_dates("modified")
        last_reg.set_text("\n".join(f"{k}: {v}" for k, v in reg.items()) or "-")
        last_mod.set_text("\n".join(f"{k}: {v}" for k, v in mod.items()) or "-")

    async def scrape(choice: str, kind: str):
        start, end = db_start.value, db_end.value
        for name in ctrl.resolve_salons(choice):
            s, e = start, end
            if not (s and e):
                # no range typed: from last saved day (inclusive, in case it was mid-day) to today
                last = ctrl.repo.latest_date(name, kind)
                s = last or dt.date.today().replace(month=1, day=1).strftime(config.DATE_FMT)
                e = dt.date.today().strftime(config.DATE_FMT)
            notice = ui.notification(f"Downloading {kind} sales for {name} {s} - {e}…",
                                     spinner=True, timeout=None)
            try:
                await ctrl.scrape_sales(name, s, e, kind)
                ui.notify(f"{name}: {kind} sales updated", type="positive")
            except Exception as ex:
                log.exception("Scrape failed")
                ui.notify(f"{name}: {ex}", type="negative", multi_line=True, timeout=0, close_button=True)
            finally:
                notice.dismiss()
        state.emit("sales_changed")

    def export_without_web(choice: str):
        try:
            payroll_start, payroll_end = current_payroll_range()
        except ValueError as ex:
            ui.notify(str(ex), type="warning")
            return
        for name in ctrl.resolve_salons(choice):
            try:
                result = ctrl.payroll(name, payroll_start, payroll_end, guarantee.value, booth.value)
                if not result.ok:
                    ui.notify(result.message, type="warning")
                    continue
                if result.unknown_employees:
                    ui.notify(f"{name}: skipped employees not in settings: "
                              f"{', '.join(result.unknown_employees)}", type="warning", multi_line=True)
                html = ctrl.export_payroll(name, payroll_start, payroll_end)
                ui.navigate.to(f"/payroll/{html.name}", new_tab=True)   # Ctrl+P there to print
                ui.notify(f"{name}: exported {html.name}", type="positive")
            except Exception as ex:
                log.exception("Export failed")
                ui.notify(f"{name}: {ex}", type="negative", multi_line=True)

    def import_dialog(kind: str):
        with ui.dialog() as dlg, ui.card().classes("w-96"):
            ui.label(f"Import Excel {kind} sales").classes("text-lg")
            salon_sel = ui.select(ctrl.salon_names(), label="Salon",
                                  value=(ctrl.salon_names() or [None])[0]).classes("w-full")

            async def handle(e):
                name, data = await read_upload(e)
                with tempfile.NamedTemporaryFile(suffix=Path(name).suffix, delete=False) as tmp:
                    tmp.write(data)
                try:
                    days = ctrl.import_sales_file(salon_sel.value, Path(tmp.name), kind)
                    ui.notify(f"Imported {days} days into {salon_sel.value}", type="positive")
                    state.emit("sales_changed")
                    dlg.close()
                except Exception as ex:
                    ui.notify(str(ex), type="negative", multi_line=True)
                finally:
                    Path(tmp.name).unlink(missing_ok=True)

            ui.upload(label="Choose .xlsx", auto_upload=True, on_upload=handle).props(
                'accept=".xlsx"').classes("w-full")
            ui.button("Cancel", on_click=dlg.close).props("flat")
        dlg.open()

    def load_settings_dialog():
        with ui.dialog() as dlg, ui.card().classes("w-[32rem]"):
            ui.label("Load settings JSON").classes("text-lg")
            path = ui.input("Path", value=str(ctrl.settings_file)).classes("w-full")

            def go():
                try:
                    ctrl.load_settings(Path(path.value))
                    state.emit("salons_changed")
                    state.emit("sales_changed")
                    ui.notify("Settings loaded", type="positive")
                    dlg.close()
                except Exception as ex:
                    ui.notify(str(ex), type="negative")
            with ui.row():
                ui.button("Load", on_click=go)
                ui.button("Cancel", on_click=dlg.close).props("flat")
        dlg.open()

    def save_settings():
        ctrl.save_settings()
        ui.notify("Saved to database", type="positive")

    # ================================================================ menu bar
    with ui.header().classes("bg-gray-900 py-0 px-2 gap-0"):
        with ui.button("File").props("flat dense no-caps color=white"):
            with ui.menu():
                ui.menu_item("Load Settings", on_click=load_settings_dialog)
                ui.separator()
                ui.menu_item("Exit", on_click=app.shutdown)
        with ui.button("Payroll").props("flat dense no-caps color=white"):
            payroll_submenu = ui.menu()     # filled with "Export w/o web: <salon>" items
        with ui.button("Import").props("flat dense no-caps color=white"):
            with ui.menu():
                ui.menu_item("Excel Sales", on_click=lambda: import_dialog("regular"))
                ui.menu_item("Excel Modified Sales", on_click=lambda: import_dialog("modified"))
        ui.button("Reporting", on_click=lambda: tabs.set_value("Reports")).props(
            "flat dense no-caps color=white")

    # ================================================================ toolbar row
    with ui.row().classes("w-full items-center gap-6 px-2 no-wrap"):
        logo = config.STATIC_DIR / "logo.png"
        if logo.is_file():
            ui.image(f"/static/{logo.name}").classes("w-16")
        else:
            ui.label("KP").classes("text-4xl font-black")
        with ui.column().classes("items-center gap-0"):
            ui.label("Sales").classes("text-xs")
            sales_btn = ui.dropdown_button(icon="storage", auto_close=True).props("size=lg")
        with ui.column().classes("gap-0"):
            ui.label("Last Date").classes("text-xs")
            last_reg = mono()
        with ui.column().classes("items-center gap-0"):
            ui.label("Modified\nSales").classes("text-xs whitespace-pre text-center")
            mod_btn = ui.dropdown_button(icon="dns", auto_close=True, color="teal").props("size=lg")
        with ui.column().classes("gap-0"):
            ui.label("Last Date").classes("text-xs")
            last_mod = mono()
        ui.space()
        ui.button(icon="save", on_click=save_settings).props("size=lg").tooltip("Save settings")
        ui.button(icon="power_settings_new", color="negative", on_click=app.shutdown).props(
            "size=lg").tooltip("Exit")

    # ================================================================ tabs
    with ui.tabs().classes("w-full") as tabs:
        for t in ("Main", "Employees", "Salon", "Reports", "Log"):
            ui.tab(t)
    with ui.tab_panels(tabs, value="Main").classes("w-full flex-grow"):
        with ui.tab_panel("Main"):
            (current_payroll_range, guarantee, booth) = build_main_tab(state, export_without_web)
        with ui.tab_panel("Employees"):
            employees_tab.build(state)
        with ui.tab_panel("Salon"):
            salon_tab.build(state)
        with ui.tab_panel("Reports"):
            reports_tab.build(state)
        with ui.tab_panel("Log"):
            log_tab.build(log_handler)

    # ================================================================ notice bar
    with ui.footer().classes("bg-gray-900 p-1"):
        notice = ui.log(max_lines=50).classes("w-full h-20 text-xs")
        log_handler.targets.append(notice)

    # ================================================================ wiring
    def rebuild_salon_menus():
        salons_menu(sales_btn, lambda n: scrape(n, "regular"))
        salons_menu(mod_btn, lambda n: scrape(n, "modified"))
        salons_menu(payroll_submenu, export_without_web, prefix="Export w/o web: ")
        refresh_last_dates()

    state.on("salons_changed", rebuild_salon_menus)
    state.on("sales_changed", refresh_last_dates)
    rebuild_salon_menus()


def build_main_tab(state: ViewState, export_without_web):
    ctrl = state.ctrl
    output_cache: dict[str, str] = {}

    def on_start_change(e):
        """Picking a start date fills end = start + 6 (Monday→Sunday)."""
        try:
            s = dt.datetime.strptime(e.value, config.DATE_FMT)
            p_end.value = (s + dt.timedelta(days=6)).strftime(config.DATE_FMT)
        except (TypeError, ValueError):
            pass

    def on_this_week(e):
        if e.value:
            p_start.value, p_end.value = week_of(dt.date.today())

    def current_range():
        if this_week.value:
            return week_of(dt.date.today())
        if not (p_start.value and p_end.value):
            raise ValueError("Choose a Payroll Date Range (or tick This Week)")
        return p_start.value, p_end.value

    def show(text: str):
        output.set_text(text)

    def fill_list(items: dict[str, str]):
        output_cache.clear()
        output_cache.update(items)
        emp_list.clear()
        with emp_list:
            for name in items:
                ui.item(name, on_click=lambda n=name: show(output_cache[n])).props("clickable dense")

    def ask_add_unknown(salon: str, names: list[str], rerun):
        with ui.dialog() as dlg, ui.card():
            ui.label(f"Found in {salon} sales but not in settings:").classes("font-bold")
            boxes = {n: ui.checkbox(n, value=True) for n in names}
            ui.label("Tick the ones to add as Regular employees (60/60).").classes("text-xs")

            def confirm():
                for n, cb in boxes.items():
                    if cb.value:
                        ctrl.add_default_employee(salon, n)
                state.emit("employees_changed")
                dlg.close()
                rerun()
            with ui.row():
                ui.button("Add & recalculate", on_click=confirm)
                ui.button("Skip them", on_click=dlg.close).props("flat")
        dlg.open()

    def run(view: str):
        salon = salon_sel.value
        try:
            start, end = current_range()
            result = ctrl.payroll(salon, start, end, guarantee.value, booth.value)
        except Exception as ex:
            ui.notify(str(ex), type="negative")
            return
        if not result.ok:
            ui.notify(result.message, type="warning")
            return
        if result.unknown_employees:
            ask_add_unknown(salon, result.unknown_employees, lambda: run(view))
        if view == "status":
            statuses = ctrl.employee_status(salon)
            show("\n".join(f"{n}:\n  {s}" for n, s in statuses.items()) or "No status data")
            fill_list({})
        elif view == "payroll":
            fill_list(result.printouts)
            show("← pick an employee")
        elif view == "details":
            if not result.details:
                ui.notify("No modified sales for this range, details unavailable", type="warning")
            fill_list(result.details)
            show("← pick an employee")

    # ---------------------------------------------------------------- layout
    with ui.row().classes("items-end gap-6"):
        with ui.column().classes("items-center gap-0"):
            ui.label("Export\nw/o web").classes("text-xs whitespace-pre text-center")
            export_btn = ui.dropdown_button(icon="web_asset_off", auto_close=True).props("size=lg")
        icon_button("View\nPayroll", "payments", lambda: run("payroll"), "orange")
        icon_button("View\nDetails", "receipt_long", lambda: run("details"), "deep-purple")
        icon_button("View\nStatus", "task_alt", lambda: run("status"), "green",
                    tooltip="Current week income status for employees")
        with ui.card().props("flat bordered").classes("p-2 gap-1"):
            ui.label("Payroll Date Range").classes("text-xs")
            p_start = date_input("Start", on_change=on_start_change)
            p_end = date_input("End")
        with ui.column().classes("gap-1"):
            this_week = ui.checkbox("This Week", on_change=on_this_week)
            guarantee = ui.checkbox("Guarantee")
            booth = ui.input("Manual Booth Rent").props("dense outlined").classes("w-40")

    with ui.row().classes("w-full no-wrap gap-4 mt-2"):
        with ui.card().classes("w-64 h-[60vh]"):
            with ui.row().classes("items-center no-wrap"):
                salon_sel = ui.select(ctrl.salon_names(), label="Salon",
                                      value=(ctrl.salon_names() or [None])[0]).classes("w-40")
                ui.button(icon="refresh", on_click=lambda: run("payroll")).props("round flat")
            ui.label("Employees").classes("self-center")
            with ui.scroll_area().classes("flex-grow"):
                emp_list = ui.list().classes("w-full")
        with ui.card().classes("flex-grow h-[60vh]"):
            with ui.scroll_area().classes("w-full h-full"):
                output = mono()

    def refresh_salons():
        names = ctrl.salon_names()
        salon_sel.set_options(names, value=salon_sel.value if salon_sel.value in names else
                              (names[0] if names else None))
        export_btn.clear()
        with export_btn:
            for n in ["All", *names]:
                ui.item(n.capitalize(), on_click=lambda n=n: export_without_web(n))

    state.on("salons_changed", refresh_salons)
    refresh_salons()
    return current_range, guarantee, booth
