"""Employees tab: form on the left, list on the right (old empTabLeftCol / empTabRightCol)."""
from __future__ import annotations

from nicegui import ui

from views.state import ViewState

ROLES = ["Regular", "Cash", "Checkdeal", "Janitor", "Owner"]
REGULAR_TYPES = ("Regular", "Janitor", "Owner")
DAYS = [("mon", "M"), ("tue", "T"), ("wed", "W"), ("thu", "Th"), ("fri", "F"), ("sat", "Sat"), ("sun", "Sun")]
RATES = [0.5, 0.6, 0.7]
CASH_RATES = [1, 0.85, 0.8, 0.75]


def _num(v, cast=float):
    try:
        return cast(v)
    except (TypeError, ValueError):
        return cast(0)


def set_choice(sel: ui.select, value) -> None:
    """ui.select rejects values not in its options; add odd rates (e.g. 0.65) on the fly."""
    if value is not None and value not in sel.options:
        sel.set_options([*sel.options, value])
    sel.value = value


def build(state: ViewState) -> None:
    ctrl = state.ctrl
    f: dict = {}          # form widgets by field name
    selected: list[str] = []

    # ---------------------------------------------------------------- form <-> dict
    def toggle_paygrade(role):
        regular = role in REGULAR_TYPES
        special = role in ("Cash", "Checkdeal")
        for k in ("commission", "check"):
            f[k].set_enabled(regular or not role)
        for k in ("commissionspecial", "checkdeal", "checkoriginal", "cashrate"):
            f[k].set_enabled(special or not role)

    def to_form(emp: dict):
        t, reg, spec = emp["type"], emp["type"].get("regular", {}), emp["type"].get("special", {})
        if emp.get("salonName") in f["salon"].options:
            f["salon"].value = emp["salonName"]
        for k in ("name", "checkName"):
            f[k].value = emp.get(k, "")
        for k in ("pay6", "pay7", "rent", "fees", "checkbonus", "checkfee", "cashbonus", "cashfee",
                  "boothcustom"):
            f[k].value = emp.get(k, 0)
        f["active"].value = emp.get("active", True)
        f["boothcustomflag"].value = emp.get("boothcustomflag", False)
        f["printchecks"].value = emp.get("printchecks", True)
        set_choice(f["role"], t.get("role", "Regular").capitalize())
        set_choice(f["commission"], reg.get("commission", 0))
        set_choice(f["check"], reg.get("check", 0))
        for k in ("commissionspecial", "checkdeal", "checkoriginal", "cashrate"):
            set_choice(f[k], spec.get(k, 0))
        for d, _ in DAYS:
            f[d].value = emp.get("workdays", {}).get(d, False)

    def from_form() -> dict:
        role = f["role"].value or ""
        regular = role in REGULAR_TYPES
        return {
            "active": f["active"].value,
            "name": " ".join((f["name"].value or "").split()),
            "checkName": " ".join((f["checkName"].value or "").split()),
            "pay6": _num(f["pay6"].value), "pay7": _num(f["pay7"].value),
            "fees": _num(f["fees"].value, int), "rent": _num(f["rent"].value, int),
            "checkbonus": _num(f["checkbonus"].value, int), "checkfee": _num(f["checkfee"].value, int),
            "cashbonus": _num(f["cashbonus"].value, int), "cashfee": _num(f["cashfee"].value, int),
            "boothcustom": _num(f["boothcustom"].value, int),
            "boothcustomflag": bool(f["boothcustomflag"].value),
            "printchecks": bool(f["printchecks"].value),
            "type": {"role": role,
                     "regular": {"commission": _num(f["commission"].value) if regular else 0,
                                 "check": _num(f["check"].value) if regular else 0},
                     "special": {k: (0 if regular else _num(f[k].value))
                                 for k in ("commissionspecial", "checkdeal", "checkoriginal", "cashrate")}},
            "workdays": {d: bool(f[d].value) for d, _ in DAYS},
        }

    def clear():
        for k in ("name", "checkName"):
            f[k].value = ""
        for k in ("pay6", "pay7", "rent", "fees", "checkbonus", "checkfee", "cashbonus", "cashfee",
                  "boothcustom", "commission", "check", "commissionspecial", "checkdeal",
                  "checkoriginal", "cashrate"):
            f[k].value = None
        f["active"].value, f["printchecks"].value, f["boothcustomflag"].value = True, True, False
        f["role"].value = None
        for d, _ in DAYS:
            f[d].value = False

    def save(must_exist: bool):
        try:
            key = ctrl.save_employee(f["salon"].value, from_form(), must_exist)
        except ValueError as ex:
            ui.notify(str(ex), type="warning")
            return
        ui.notify(f"{'Updated' if must_exist else 'Saved'} {key} in {f['salon'].value} "
                  f"(click 💾 to write to disk)", type="positive")
        refresh_list()

    def remove():
        if not selected:
            ui.notify("Select employee(s) in the list first", type="warning")
            return
        with ui.dialog() as dlg, ui.card():
            ui.label(f"Delete {', '.join(selected)} from {list_salon.value}?")
            def yes():
                ctrl.remove_employees(list_salon.value, list(selected))
                selected.clear()
                refresh_list()
                dlg.close()
            with ui.row():
                ui.button("Delete", color="negative", on_click=yes)
                ui.button("Cancel", on_click=dlg.close).props("flat")
        dlg.open()

    # ---------------------------------------------------------------- list
    def pick(name: str, multi: bool):
        if multi:
            selected.remove(name) if name in selected else selected.append(name)
        else:
            selected[:] = [name]
            to_form(ctrl.employees(list_salon.value)[name])
        refresh_list(keep_selection=True)

    def refresh_list(keep_selection: bool = False):
        if not keep_selection:
            selected.clear()
        emp_list.clear()
        if not list_salon.value:
            return
        with emp_list:
            for name, info in ctrl.employees(list_salon.value, active_only.value).items():
                item = ui.item()
                item.on("click", lambda e, n=name: pick(n, bool(e.args.get("ctrlKey"))), ["ctrlKey"])
                item.props("clickable dense" + (" active" if name in selected else ""))
                with item:
                    with ui.item_section():
                        ui.item_label(name)
                    with ui.item_section().props("side"):
                        ui.item_label(info["type"]["role"]).props("caption")
                        if not info["active"]:
                            ui.item_label("inactive").props("caption").classes("text-red-400")

    # ---------------------------------------------------------------- layout
    names = ctrl.salon_names()
    first = names[0] if names else None
    with ui.row().classes("w-full no-wrap gap-4 items-start"):
        with ui.card().classes("w-[36rem]"):
            with ui.row().classes("items-center w-full"):
                f["salon"] = ui.select(names, label="Salon", value=first).classes("w-40")
                f["active"] = ui.switch("Active", value=True)
            f["name"] = ui.input("Name").classes("w-full")
            f["checkName"] = ui.input("Name on check").classes("w-full")
            with ui.grid(columns=2).classes("w-full"):
                for key, label in [("pay6", "Pay 6 Day"), ("pay7", "Pay 7th Day"), ("rent", "Rent / Week"),
                                   ("fees", "Fees / Day"), ("checkbonus", "Check Bonus"),
                                   ("checkfee", "Check Fee"), ("cashbonus", "Cash Bonus"),
                                   ("cashfee", "Cash Fee")]:
                    f[key] = ui.number(label).props("dense")
            with ui.row().classes("items-center"):
                f["boothcustomflag"] = ui.checkbox("Custom Booth")
                f["boothcustom"] = ui.number("Booth amount").props("dense")

            with ui.card().props("flat bordered").classes("w-full"):
                ui.label("Pay Type").classes("font-bold")
                f["role"] = ui.select(ROLES, label="Role",
                                      on_change=lambda e: toggle_paygrade(e.value)).classes("w-40")
                ui.label("Regular").classes("italic")
                with ui.row():
                    f["commission"] = ui.select(RATES, label="Commission", new_value_mode="add-unique").classes("w-32")
                    f["check"] = ui.select(RATES, label="Check", new_value_mode="add-unique").classes("w-32")
                ui.label("Special").classes("italic")
                with ui.row():
                    f["commissionspecial"] = ui.select(RATES, label="Commission",
                                                       new_value_mode="add-unique").classes("w-32")
                    f["cashrate"] = ui.select(CASH_RATES, label="Cash Rate",
                                              new_value_mode="add-unique").classes("w-32")
                    f["checkoriginal"] = ui.select(RATES, label="Check Original",
                                                   new_value_mode="add-unique").classes("w-32")
                    f["checkdeal"] = ui.select(RATES, label="Check Deal",
                                               new_value_mode="add-unique").classes("w-32")
                f["printchecks"] = ui.checkbox("Print Checks", value=True)

            ui.label("Work Days (if Janitor)")
            with ui.row():
                for d, label in DAYS:
                    f[d] = ui.checkbox(label)
            with ui.row().classes("w-full justify-around"):
                ui.button("Save New", icon="person_add", on_click=lambda: save(False))
                ui.button("Clear Form", icon="backspace", on_click=clear).props("outline")
                ui.button("Update Existing", icon="save_as", on_click=lambda: save(True))

        with ui.card().classes("flex-grow h-[75vh]"):
            with ui.row().classes("items-center"):
                list_salon = ui.select(names, label="Choose Salon", value=first,
                                       on_change=lambda: refresh_list()).classes("w-40")
                ui.button(icon="refresh", on_click=lambda: refresh_list()).props("round flat")
                active_only = ui.checkbox("Show Active Only", value=True, on_change=lambda: refresh_list())
            ui.label("Click to edit · Ctrl+click to multi-select for delete").classes("text-xs opacity-60")
            with ui.scroll_area().classes("flex-grow w-full"):
                emp_list = ui.list().classes("w-full")
            with ui.row().classes("w-full justify-end"):
                ui.button(icon="delete", color="negative", on_click=remove).tooltip("Delete employee(s)")

    def refresh_salons():
        names = ctrl.salon_names()
        for sel in (f["salon"], list_salon):
            sel.set_options(names, value=sel.value if sel.value in names else (names[0] if names else None))
        refresh_list()

    toggle_paygrade(None)
    state.on("salons_changed", refresh_salons)
    state.on("employees_changed", refresh_list)
    refresh_list()
