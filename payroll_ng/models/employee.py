"""
Employee models. Pure business logic: no GUI, no file I/O.
Ported from Employee.py. Calculation logic and the data layout of master.json are unchanged,
so existing settings load as-is.

Steps when adding a new employee field:
    1. Employee.__init__  (read it from data with a default)
    2. Employee.get_info  (write it back out for saving)
    3. views/employees_tab.py  FIELDS / form
"""
from __future__ import annotations

import datetime
import math
import string

DEFAULT_WORKDAYS = {d: False for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
REGULAR_ROLES = ("regular", "owner")
WEEKDAY_KEYS = {1: "mon", 2: "tue", 3: "wed", 4: "thu", 5: "fri", 6: "sat", 7: "sun"}


def _num(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class Employee:
    def __init__(self, data: dict):
        t = data.get("type", {})
        reg = t.get("regular", {})
        spec = t.get("special", {})
        self.name = data.get("name", "")
        self.checkName = data.get("checkName", "")
        self.salonName = data.get("salonName", "")
        self.pay6 = data.get("pay6", 0)
        self.pay7 = data.get("pay7", 0)
        self.rent = data.get("rent", 0)
        self.fees = data.get("fees", 0)
        self.checkbonus = data.get("checkbonus", 0)
        self.checkfee = data.get("checkfee", 0)
        self.cashbonus = data.get("cashbonus", 0)
        self.cashfee = data.get("cashfee", 0)
        self.active = data.get("active", True)
        self.role = t.get("role", "Regular")
        self.commission = reg.get("commission", 0)
        self.check = reg.get("check", 0.6)
        self.commissionspecial = spec.get("commissionspecial", 0)
        self.checkdeal = spec.get("checkdeal", 0)
        self.checkoriginal = spec.get("checkoriginal", 0.6)
        self.cashrate = spec.get("cashrate", 0)
        self.printchecks = data.get("printchecks", True)
        self.boothcustom = data.get("boothcustom", 0)
        self.boothcustomflag = data.get("boothcustomflag", False)
        self.workdays = {**DEFAULT_WORKDAYS, **data.get("workdays", {})}
        self.warnings: list[str] = []   # collected instead of popping up dialogs
        self._reset_results()

    # ------------------------------------------------------------------ helpers
    @property
    def is_regular_type(self) -> bool:
        return self.role.lower() in REGULAR_ROLES

    @property
    def rate(self) -> float:
        return self.commission if self.is_regular_type else self.commissionspecial

    @property
    def check_rate(self) -> float:
        return self.check if self.is_regular_type else self.checkoriginal

    def _reset_results(self):
        self.sales: dict = {}
        self.modifiedSales: dict = {}
        self.boothrent = 0
        self.modSummary = {"total": 0, "tips": 0, "commission": 0, "check": 0}
        self.paySummary = {"total": 0, "commission": 0, "check": 0, "cash": 0,
                           "basepaycheck": 0, "basepaycash": 0, "paycheck": 0, "paycash": 0,
                           "tips": 0, "fees": 0, "daysworked": 0, "metGoal": False}
        self.xlreport = {"check": 0, "checkdeal": 0, "cash": 0, "booth": 0, "bcheck": 0, "bcash": 0}
        self.payPrint = ""
        self.modSales = ""

    # ------------------------------------------------------------------ payroll
    def calculate_payroll(self, sales, modified_sales, fee_days, guarantee, booth):
        self._reset_results()
        self.warnings.clear()
        self.sales = dict(sales)
        if modified_sales:
            self.modifiedSales = dict(modified_sales)
        self._generic_calculate(fee_days, guarantee, booth)
        return True, ""

    def _generic_calculate(self, fee_days, guarantee, booth):
        tips = commission_sales = total_sales = days_worked = personal_fees = 0
        mod_sales = mod_tips = mod_commission = 0
        rate = self.rate

        out = f'{"  " + string.capwords(self.salonName) + "  ":=^30}\n'
        out += f"{self.name:<40}\n"
        out += f'{" Daily ":-^30}\n'
        out += f'{"Day":<12}{"Sales":>8}{"Tips":>8}\n'
        out_m = f'{"  " + string.capwords(self.salonName) + "  ":=^60}\n'
        out_m += f"{self.name:<60}\n"
        out_m += f'{"Day":<17}{"Sales":>10}{"Tips":>10}{" | "}{"MSales":>10}{"MTips":>10}\n'

        for day, amt in sorted(self.sales.items()):
            if fee_days.get(WEEKDAY_KEYS[day.isoweekday()]):
                personal_fees += self.fees
            m = self.modifiedSales.get(day, {}) if self.modifiedSales else {}
            m_sales, m_tip, m_comm = m.get("sales", 0), m.get("tips", 0), m.get("commission", 0)

            day_sales = amt.get("sales", 0) or 0
            day_tip = amt.get("tips", 0) or 0
            tips += day_tip
            commission_sales += day_sales * rate
            total_sales += day_sales
            mod_commission += m_comm
            mod_sales += m_sales
            mod_tips += m_tip
            if day_sales > 0:
                days_worked += 1
            d = day.strftime("%m/%d:%a")
            out += f"{d:<12}{day_sales:>8.2f}{day_tip:>8.2f}\n"
            out_m += f'{d:<17}{day_sales:>10.2f}{day_tip:>10.2f}{" | "}{m_sales:>10.2f}{m_tip:>10.2f}\n'

        out += f'{" ":12}{"-":->16}\n{" ":12}{total_sales:>8.2f}{tips:>8.2f}\n\n'
        out += f'{" Summary ":-^30}\n'
        out += f'{"Total Sale":<10}{" ":5}{total_sales:>10.2f}\n'
        out += f'{"Commission":<10}{" ":5}{commission_sales:>10.2f}\n'
        out += f'{"Tips":<10}{" ":5}{tips:>10.2f}\n'
        out += f'{" ":15}{"-":->10}\n'
        out += f'{"Sales Pay":<10}{" ":5}{commission_sales + tips:>10.2f}\n'
        out += f'{"=":=^30}\n\n'
        out_m += f'{" ":12}{"-":->20}{" | "}{" ":->20}\n'
        out_m += f'{" ":12}{total_sales:>10.2f}{tips:>10.2f}{" | "}{mod_sales:>10.2f}{mod_tips:>10.2f}\n\n\n'
        out_m += f'{"":*^60}\n{" Summary ":-^60}\n'
        out_m += f'{"Total Sale":<15}{total_sales:>10.2f}{" | "}{"M Sale":<15}{mod_sales:>10.2f}\n'
        out_m += f'{"Commission":<15}{commission_sales:>10.2f}{" | "}{"M Commission":<15}{mod_commission:>10.2f}\n'
        out_m += f'{"Tips":<15}{tips:>10.2f}{" | "}{"M Tips":<15}{mod_tips:10.2f}\n'
        out_m += f'{" ":15}{"-":->10}{" | "}{" ":15}{"-":->10}\n'
        out_m += (f'{"Sales Pay":<15}{commission_sales + tips:>10.2f}{" | "}'
                  f'{"M Sales Pay":<15}{mod_commission + mod_tips:>10.2f}\n')
        out_m += f'{"=":=^60}\n\n\n'

        check_rate = self.check_rate
        check = commission_sales * check_rate
        cash = commission_sales - check

        # base pay (bao luong)
        base_per_day = self.pay6 / 6 if self.pay6 else 0
        base_for_range = base_per_day * days_worked
        basepaycheck = basepaycash = 0
        if days_worked == 6:
            basepaycheck = self.pay6 * check_rate
            basepaycash = self.pay6 - basepaycheck
        elif days_worked == 7:
            full = self.pay6 + self.pay7
            base_for_range = full
            basepaycheck = full * check_rate
            basepaycash = full - basepaycheck
        elif guarantee:
            basepaycheck = base_for_range * check_rate
            basepaycash = base_for_range - basepaycheck
        met_goal = commission_sales >= base_for_range

        ps = self.paySummary
        ps.update(total=total_sales, commission=commission_sales, check=check, cash=cash,
                  basepaycheck=basepaycheck, basepaycash=basepaycash, tips=tips,
                  fees=personal_fees, daysworked=days_worked, metGoal=met_goal)
        self.modSummary.update(total=mod_sales, tips=mod_tips, commission=mod_commission,
                               check=mod_commission + mod_tips)

        if days_worked >= 6 or guarantee:
            ps["paycheck"] = check if met_goal else basepaycheck
            ps["paycash"] = cash if met_goal else basepaycash
        else:
            ps["paycheck"], ps["paycash"] = check, cash

        x = self.xlreport
        x["check"] = ps["paycheck"] + tips + self.checkbonus - self.checkfee
        x["cash"] = ps["paycash"] - personal_fees - self.rent + self.cashbonus - self.cashfee

        # booth rent priority: personal custom > manual salon value > modified-sales difference
        if self.boothcustomflag:
            try:
                self.boothrent = float(self.boothcustom)
            except (TypeError, ValueError):
                self.warnings.append(f"Custom booth rent for {self.name} is not a number; using 0.")
                self.boothrent = 0
        elif booth not in (None, "", 0):
            self.boothrent = _num(booth)
        elif self.modifiedSales:
            self.boothrent = self.modSummary["check"] - x["check"]
        x["booth"] = self.boothrent
        x["bcheck"] = x["check"] + self.boothrent
        x["bcash"] = x["cash"] - self.boothrent

        o = f'{"OptionA":<12}    {ps["paycheck"]:>10.2f}\n'
        o += f'{"Tips":<12}  + {tips:>10.2f}\n'
        if self.checkbonus:
            o += f'{"Bonus":<12}  + {self.checkbonus:>10.2f}\n'
        if self.checkfee:
            o += f'{"Fee":<12}  - {self.checkfee:>10.2f}\n'
        o += f'{" ":<12}  {"":-^12}\n{" ":<12}    {x["check"]:>10.2f}\n'
        o += f'{"SSF":<12}  + {self.boothrent:>10.2f}\n{" ":<12}  {"":=^12}\n'
        o += f'{"OptA Total":<12}    {math.ceil(x["check"] + self.boothrent):>10.2f}\n\n\n'
        o += f'{"OptionB":<12}    {ps["paycash"]:>10.2f}\n'
        o += f'{"Fees":<12}  - {personal_fees + self.rent:>10.2f}\n'
        if self.cashbonus:
            o += f'{"Bonus":<12}  + {self.cashbonus:>10.2f}\n'
        if self.cashfee:
            o += f'{"Fee2":<12}  - {self.cashfee:>10.2f}\n'
        o += f'{" ":<12}  {"":-^12}\n{" ":<12}    {x["cash"]:>10.2f}\n'
        o += f'{"SSF":<12}  - {self.boothrent:>10.2f}\n{" ":<12}  {"":=^12}\n'
        o += f'{"OptB Total":<12}    {math.ceil(x["bcash"]):>10.2f}\n\n'
        self.payPrint = out + o
        self.modSales = out_m + o

    # ------------------------------------------------------------------ getters
    def get_status(self):
        """Progress for the current week. (Old version read a missing 'totalsale' key and always failed.)"""
        if not self.rate:
            return None
        ps = self.paySummary
        return {"total": math.ceil(ps["total"]), "comm": math.ceil(ps["commission"]),
                "tips": math.ceil(ps["tips"]), "daysWorked": ps["daysworked"], "metGoal": ps["metGoal"]}

    def get_info(self) -> dict:
        return {"active": self.active, "salonName": self.salonName, "name": self.name,
                "checkName": self.checkName, "rent": self.rent, "fees": self.fees,
                "pay6": self.pay6, "pay7": self.pay7,
                "checkbonus": self.checkbonus, "checkfee": self.checkfee,
                "cashbonus": self.cashbonus, "cashfee": self.cashfee,
                "boothcustom": self.boothcustom, "boothcustomflag": self.boothcustomflag,
                "printchecks": self.printchecks,
                "type": {"role": self.role,
                         "regular": {"commission": self.commission, "check": self.check},
                         "special": {"commissionspecial": self.commissionspecial,
                                     "checkdeal": self.checkdeal,
                                     "checkoriginal": self.checkoriginal, "cashrate": self.cashrate}},
                "workdays": dict(self.workdays)}


class EmployeeSpecial(Employee):
    """Checkdeal / Cash employees: check amount written differs from reported amount."""

    def calculate_payroll(self, sales, modified_sales, fee_days, guarantee, booth):
        super().calculate_payroll(sales, modified_sales, fee_days, guarantee, booth)
        ps, x = self.paySummary, self.xlreport
        out = f'{"*":*^30}\n'
        role = self.role.lower()
        if role == "checkdeal":
            totalpay = ps["paycheck"] + ps["paycash"]
            paycheckdeal = totalpay * self.checkdeal
            paycashdeal = totalpay - paycheckdeal
            x["checkdeal"] = paycheckdeal + ps["tips"] + x["booth"] + self.checkbonus - self.checkfee
            x["bcheck"] = x["check"] + x["booth"]
            x["bcash"] = (paycashdeal - ps["fees"] - self.rent + self.cashbonus
                          - self.cashfee - self.boothrent)
            out += f'{"Check Deal":<15}    {paycheckdeal:>10.2f}\n'
            out += f'{"Tips":<15}  + {ps["tips"]:>10.2f}\n'
            paycheckdeal += ps["tips"]
            if self.checkbonus:
                out += f'{"Bonus":<15}  + {self.checkbonus:>10.2f}\n'
                paycheckdeal += self.checkbonus
            if self.checkfee:
                out += f'{"Fee":<15}  - {self.checkfee:>10.2f}\n'
                paycheckdeal -= self.checkfee
            out += f'{" ":<15}  {"":-^12}\n{" ":<15}    {paycheckdeal:>10.2f}\n'
            out += f'{"MS":<15}  + {self.boothrent:>10.2f}\n{" ":<15}  {"":=^12}\n'
            out += f'{"OptA Total":<15}    {math.ceil(x["checkdeal"]):>10.2f}\n\n'
            out += f'{"OptB":<15}    {paycashdeal:>10.2f}\n'
            out += f'{"Fees":<15}  - {ps["fees"] + self.rent:>10.2f}\n'
            paycashdeal -= ps["fees"] + self.rent
            if self.cashbonus:
                out += f'{"Bonus":<15}  + {self.cashbonus:>10.2f}\n'
                paycashdeal += self.cashbonus
            if self.cashfee:
                out += f'{"Fee2":<15}  - {self.cashfee:>10.2f}\n'
                paycashdeal -= self.cashfee
            out += f'{" ":<15}  {"":-^12}\n{" ":<15}    {paycashdeal:>10.2f}\n'
            out += f'{"MS":<15}  - {self.boothrent:>10.2f}\n{" ":<15}  {"":=^12}\n'
            out += f'{"OptB Total":<15}    {math.ceil(x["bcash"]):>10.2f}\n\n'
        elif role == "cash":
            cashdeal = float(x["check"] * self.cashrate)
            x["bcash"] = math.ceil(x["cash"] + cashdeal)
            x["bcheck"] = 0
            out += f'{"Check Qua Tien Mat:":<25}{cashdeal:<10.2f}\n'
            out += f'{"Tien Mat:":<25}{x["cash"]:<10.2f}\n'
            out += f'{"Ca hai cong loi:":<25}{x["bcash"]:<10}\n\n'
        self.payPrint += out
        self.modSales += out
        return True, ""


class EmployeeJanitor(Employee):
    def calculate_payroll(self, sales=None, modified_sales=None, fee_days=None, guarantee=None, booth=None):
        self._reset_results()
        days = sum(1 for worked in self.workdays.values() if worked)
        week_pay = (self.pay6 / 6) * days
        x = self.xlreport
        x["bcheck"] = math.ceil(week_pay * self.check)
        x["bcash"] = math.ceil(week_pay - x["bcheck"])
        if x["bcash"] == 0:
            x["bcheck"] -= self.rent
        else:
            x["bcash"] -= self.rent
        self.payPrint = f'Check: {x["bcheck"]}    Cash: {x["bcash"]}'
        return True, ""


def make_employee(data: dict) -> Employee:
    """Factory: picks the right class from the role (case-insensitive, unlike the old code)."""
    role = data.get("type", {}).get("role", "Regular").lower()
    if role in ("checkdeal", "cash"):
        return EmployeeSpecial(data)
    if role == "janitor":
        return EmployeeJanitor(data)
    return Employee(data)
