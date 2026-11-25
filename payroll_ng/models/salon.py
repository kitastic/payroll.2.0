"""
Salon model: settings + employees + payroll orchestration.
Old Salon inherited from Bot (the browser). Here scraping lives in services/zota_scraper.py and
file storage in services/sales_repo.py, so this class only holds data and does math.
"""
from __future__ import annotations

import string
from dataclasses import dataclass, field

from models.employee import Employee, make_employee


def norm(name: str) -> str:
    """Zota names sometimes carry extra spaces; compare on this."""
    return string.capwords(" ".join(str(name).split()))


@dataclass
class PayrollResult:
    ok: bool
    message: str = ""
    printouts: dict[str, str] = field(default_factory=dict)
    details: dict[str, str] = field(default_factory=dict)
    unknown_employees: list[str] = field(default_factory=list)   # in sales but not in settings
    warnings: list[str] = field(default_factory=list)


class Salon:
    def __init__(self, bundle: dict):
        self.name: str = bundle["name"]
        self.username: str = bundle.get("login", {}).get("username", "")
        self.password: str = bundle.get("login", {}).get("password", "")
        self.active: bool = bundle.get("active", True)
        self.path: str = bundle.get("path", "../db/")
        self.payments_fnames = bundle.get("paymentsFnames", {})
        self.employees: dict[str, Employee] = {
            norm(k): make_employee(v) for k, v in bundle.get("employees", {}).items()
        }

    # ------------------------------------------------------------ employees
    def upsert_employee(self, data: dict) -> str:
        key = norm(data["name"])
        data = {**data, "name": key, "salonName": self.name}
        self.employees[key] = make_employee(data)
        return key

    def add_default_employee(self, name: str) -> str:
        return self.upsert_employee({
            "name": name, "active": True, "boothcustomflag": True,
            "type": {"role": "Regular", "regular": {"commission": 0.6, "check": 0.6}},
        })

    def remove_employee(self, name: str) -> None:
        self.employees.pop(name, None)

    def employee_infos(self, active_only: bool = False) -> dict[str, dict]:
        return {k: e.get_info() for k, e in sorted(self.employees.items())
                if e.active or not active_only}

    # ------------------------------------------------------------ payroll
    def calculate_payroll(self, week: dict, modified_week: dict, guarantee: bool, booth) -> PayrollResult:
        """
        week / modified_week: {datetime: {emp_name: {...}}} straight from SalesRepo.get_range.
        Unknown employees are reported back instead of popping a dialog here.
        """
        if not week:
            return PayrollResult(False, f"{self.name}: no sales data in that date range")

        by_emp: dict[str, dict] = {}
        for day, emps in week.items():
            for emp, totals in emps.items():
                by_emp.setdefault(norm(emp), {})[day] = totals
        by_emp_mod: dict[str, dict] = {}
        for day, emps in (modified_week or {}).items():
            for emp, totals in emps.items():
                by_emp_mod.setdefault(norm(emp), {})[day] = totals

        result = PayrollResult(True)
        result.unknown_employees = [n for n in by_emp if n not in self.employees]

        # janitors first: their work days decide which days carry clean-up fees
        fee_days = {d: False for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
        for key, emp in self.employees.items():
            emp._reset_results()
            if emp.role.lower() == "janitor":
                fee_days.update(emp.workdays)
                emp.calculate_payroll()
                result.printouts[key] = emp.payPrint

        for key, sales in by_emp.items():
            emp = self.employees.get(key)
            if emp is None or emp.role.lower() == "janitor":
                continue
            emp.calculate_payroll(sales, by_emp_mod.get(key), fee_days, guarantee, booth)
            result.printouts[key] = emp.payPrint
            if modified_week:
                result.details[key] = emp.modSales
            result.warnings += emp.warnings
        return result

    def payable_employees(self) -> dict[str, Employee]:
        """Active, and either janitor or had commission this run (old exportPayroll filter)."""
        return {k: e for k, e in self.employees.items()
                if e.active and (e.role.lower() == "janitor" or e.paySummary["commission"] != 0)}

    def printable_slips(self) -> dict[str, str]:
        return {k: e.payPrint for k, e in self.payable_employees().items()
                if len(e.payPrint) > 5 and e.role.lower() not in ("janitor", "owner")}

    def statuses(self) -> dict[str, dict]:
        return {k: s for k, e in self.employees.items() if (s := e.get_status())}

    # ------------------------------------------------------------ persistence
    def to_dict(self) -> dict:
        return {"name": self.name,
                "login": {"username": self.username, "password": self.password},
                "active": self.active, "path": self.path,
                "employees": {k: e.get_info() for k, e in self.employees.items()},
                "paymentsFnames": self.payments_fnames}
