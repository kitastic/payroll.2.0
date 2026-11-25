"""Reports tab: sales over time, or year-over-year comparison (old graph / graphCompare)."""
from __future__ import annotations

import datetime as dt

from nicegui import ui

from views.state import ViewState
from views.widgets import date_input


def build(state: ViewState) -> None:
    ctrl = state.ctrl
    year = dt.date.today().year

    def load():
        try:
            labels, series = ctrl.report_series(salon.value, start.value, end.value,
                                                freq.value, compare.value)
        except Exception as ex:
            ui.notify(str(ex), type="warning")
            return
        chart.options["xAxis"]["data"] = labels
        chart.options["series"] = [
            {"name": n, "type": "line", "data": v, "smooth": True,
             "markPoint": {"data": [{"type": "max", "name": "Max"}]}}
            for n, v in series.items()
        ]
        chart.options["title"]["text"] = f"{freq.value} sales {start.value} – {end.value}"
        chart.update()

    with ui.card().props("flat bordered").classes("w-full"):
        with ui.row().classes("items-end gap-6"):
            salon = ui.select(["all", *ctrl.salon_names()], label="Salon", value="all").classes("w-40")
            start = date_input("Start", f"01/01/{year - 1}")
            end = date_input("End", dt.date.today().strftime("%m/%d/%Y"))
            freq = ui.select(["Daily", "Weekly", "Monthly", "Yearly"], label="Frequency",
                             value="Monthly").classes("w-32")
            compare = ui.checkbox("Self-comparison (by year)")
            ui.button(icon="refresh", on_click=load).props("round")

    chart = ui.echart({
        "title": {"text": "", "textStyle": {"color": "#ccc", "fontSize": 14}},
        "tooltip": {"trigger": "axis"},
        "legend": {"top": 25, "textStyle": {"color": "#ccc"}},
        "toolbox": {"feature": {"saveAsImage": {}, "dataZoom": {}, "restore": {}}},
        "dataZoom": [{"type": "inside"}, {"type": "slider"}],
        "xAxis": {"type": "category", "data": []},
        "yAxis": {"type": "value", "name": "Sales $"},
        "series": [],
    }).classes("w-full h-[60vh]")

    state.on("salons_changed", lambda: salon.set_options(["all", *ctrl.salon_names()], value="all"))
