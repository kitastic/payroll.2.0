"""Salon tab: add / update / remove salons and their Zota login."""
from __future__ import annotations

from nicegui import ui

from views.state import ViewState
from views.widgets import mono


def build(state: ViewState) -> None:
    ctrl = state.ctrl

    def load():
        if not pick.value:
            return
        info = ctrl.salon_info(pick.value)
        name.value, uname.value, pw.value, active.value = (info["name"], info["username"],
                                                           info["password"], info["active"])
        display.set_text(info["summary"])

    def do(action):
        try:
            action(name.value, uname.value, pw.value, active.value)
        except ValueError as ex:
            ui.notify(str(ex), type="warning")
            return
        state.emit("salons_changed")
        ui.notify("Done (click 💾 to write to disk)", type="positive")

    def remove():
        target = pick.value
        if not target:
            return
        with ui.dialog() as dlg, ui.card():
            ui.label(f"Remove salon '{target}' and all its employee settings?")
            def yes():
                ctrl.remove_salon(target)
                state.emit("salons_changed")
                dlg.close()
            with ui.row():
                ui.button("Remove", color="negative", on_click=yes)
                ui.button("Cancel", on_click=dlg.close).props("flat")
        dlg.open()

    def clear():
        name.value = uname.value = pw.value = ""
        active.value = True

    with ui.row().classes("w-full no-wrap gap-4 items-start"):
        with ui.card().classes("w-96"):
            with ui.row().classes("items-center no-wrap w-full"):
                pick = ui.select(ctrl.salon_names(active_only=False), label="Current Salons",
                                 on_change=load).classes("flex-grow")
                ui.button(icon="refresh", on_click=load).props("round flat")
            ui.separator()
            ui.icon("password", size="xl").classes("self-center")
            name = ui.input("Salon Name").classes("w-full")
            uname = ui.input("Username").classes("w-full")
            pw = ui.input("Password", password=True, password_toggle_button=True).classes("w-full")
            active = ui.checkbox("Active", value=True)
            with ui.row().classes("w-full justify-around"):
                ui.button("Add", icon="add_business", on_click=lambda: do(ctrl.add_salon))
                ui.button("Update", icon="save_as", on_click=lambda: do(ctrl.update_salon))
                ui.button("Clear", icon="backspace", on_click=clear).props("outline")
                ui.button("Remove", icon="delete", color="negative", on_click=remove)
        with ui.card().classes("flex-grow h-[70vh]"):
            with ui.scroll_area().classes("w-full h-full"):
                display = mono()

    state.on("salons_changed",
             lambda: pick.set_options(ctrl.salon_names(active_only=False),
                                      value=pick.value if pick.value in ctrl.salons else None))
