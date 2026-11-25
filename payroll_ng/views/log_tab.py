"""Log tab: full app log (replaces the Multiline that rerouted stdout)."""
from nicegui import ui

from views.widgets import UiLogHandler


def build(handler: UiLogHandler) -> None:
    log_view = ui.log(max_lines=2000).classes("w-full h-[70vh] font-mono text-xs")
    handler.targets.append(log_view)
    ui.button("Clear", icon="clear_all", on_click=log_view.clear).props("flat")
