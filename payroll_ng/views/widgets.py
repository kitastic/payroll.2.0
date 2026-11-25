"""Small reusable UI pieces shared by the tabs."""
from __future__ import annotations

import logging
from typing import Callable

from nicegui import ui


def date_input(label: str, value: str = "", on_change: Callable | None = None) -> ui.input:
    """Text input with a calendar popup (replaces sg.popup_get_date). Value is mm/dd/yyyy."""
    with ui.input(label, value=value, placeholder="mm/dd/yyyy").props("dense outlined").classes("w-40") as inp:
        with ui.menu().props("no-parent-event") as menu:
            with ui.date(mask="MM/DD/YYYY").bind_value(inp):
                with ui.row().classes("justify-end"):
                    ui.button("Close", on_click=menu.close).props("flat")
        with inp.add_slot("prepend"):
            ui.icon("event").on("click", menu.open).classes("cursor-pointer")
    if on_change:
        inp.on_value_change(on_change)
    return inp


def icon_button(label: str, icon: str, on_click=None, color: str = "primary", tooltip: str = ""):
    """Big labelled icon button like the old toolbar images."""
    with ui.column().classes("items-center gap-0"):
        ui.label(label).classes("text-xs text-center whitespace-pre leading-tight")
        btn = ui.button(icon=icon, on_click=on_click, color=color).props("size=lg unelevated")
        if tooltip:
            btn.tooltip(tooltip)
    return btn


def mono(text: str = "") -> ui.label:
    return ui.label(text).classes("font-mono whitespace-pre text-sm")


class UiLogHandler(logging.Handler):
    """Sends python logging into one or more ui.log widgets (Log tab + bottom notice bar)."""

    def __init__(self):
        super().__init__()
        self.targets: list[ui.log] = []
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s  %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        for t in list(self.targets):
            try:
                t.push(msg)
            except Exception:          # client disconnected
                self.targets.remove(t)
