"""
AppController: the new `Ai`. Views call only this; it calls models and services.
Methods return plain data or raise ValueError/RuntimeError with a message the view can show.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import shutil
from pathlib import Path

import pandas as pd

import config
from models.salon import PayrollResult, Salon
from services.exporter import append_rows_to_book, build_1099_rows, write_payroll_html
from services.sales_parser import parse_sales_xlsx
from services.sales_repo import SalesRepo
from services.zota_scraper import ZotaScraper

log = logging.getLogger("payroll")
FMT = config.DATE_FMT


def week_of(day: dt.date) -> tuple[str, str]:
    start = day - dt.timedelta(days=day.weekday())
    return start.strftime(FMT), (start + dt.timedelta(days=6)).strftime(FMT)


def check_range(start: str, end: str) -> tuple[str, str]:
    try:
        s, e = dt.datetime.strptime(start, FMT), dt.datetime.strptime(end, FMT)
    except (TypeError, ValueError):
        raise ValueError("Dates must be mm/dd/yyyy")
    if s > e:
        raise ValueError("Start date is after end date")
    return s.strftime(FMT), e.strftime(FMT)


def split_range(start: str, end: str, max_days: int = 180) -> list[tuple[str, str]]:
    """Zota chokes on long ranges; break them into ≤max_days chunks (old View.splitRange)."""
    s, e = dt.datetime.strptime(start, FMT), dt.datetime.strptime(end, FMT)
    chunks = []
    while s <= e:
        c_end = min(s + dt.timedelta(days=max_days - 1), e)
        chunks.append((s.strftime(FMT), c_end.strftime(FMT)))
        s = c_end + dt.timedelta(days=1)
    return chunks


class AppController:
    def __init__(self, settings_file: Path = config.MASTER_JSON, headless: bool = True):
        self.settings_file = Path(settings_file)
        self.repo = SalesRepo(config.DB_DIR)
        self.scraper = ZotaScraper(headless=headless)
        self.salons: dict[str, Salon] = {}
        self.last_payroll: dict[str, PayrollResult] = {}
        self.load_settings()

    # ============================================================ settings
    def load_settings(self, path: Path | None = None) -> None:
        path = Path(path or self.settings_file)
        if not path.is_file():
            log.warning("No settings at %s - starting empty", path)
            self.salons = {}
            return
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.salons = {name: Salon(bundle) for name, bundle in data.items()}
        self.settings_file = path
        log.info("Loaded %d salons from %s", len(self.salons), path.name)

    def save_settings(self) -> None:
        if self.settings_file.is_file():   # keep one backup in case a save goes wrong
            shutil.copy2(self.settings_file, self.settings_file.with_suffix(".json.bak"))
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump({n: s.to_dict() for n, s in self.salons.items()}, f, indent=4, sort_keys=True)
        log.info("Saved settings to %s", self.settings_file.name)

    # ============================================================ salons
    def salon_names(self, active_only: bool = True) -> list[str]:
        return [n for n, s in self.salons.items() if s.active or not active_only]

    def salon(self, name: str) -> Salon:
        if name not in self.salons:
            raise ValueError(f"Unknown salon '{name}'")
        return self.salons[name]

    def resolve_salons(self, choice: str) -> list[str]:
        return self.salon_names() if choice.lower() == "all" else [self.salon(choice).name]

    def salon_info(self, name: str) -> dict:
        s = self.salon(name)
        return {"name": s.name, "username": s.username, "password": s.password, "active": s.active,
                "summary": f"path: {s.path}\nactive: {s.active}\npaymentsFnames: {s.payments_fnames}\n"
                           f"employees:\n" + "".join(f"  {e}\n" for e in s.employees)}

    def add_salon(self, name: str, username: str, password: str, active: bool) -> None:
        name = name.strip().lower()
        if not name:
            raise ValueError("Salon name is required")
        if name in self.salons:
            raise ValueError(f"Salon '{name}' already exists - use Update")
        self.salons[name] = Salon({"name": name, "login": {"username": username, "password": password},
                                   "active": active, "path": "../db/", "employees": {},
                                   "paymentsFnames": {}})

    def update_salon(self, name: str, username: str, password: str, active: bool) -> None:
        s = self.salon(name)
        s.username, s.password, s.active = username, password, active

    def remove_salon(self, name: str) -> None:
        self.salons.pop(name, None)

    # ============================================================ employees
    def employees(self, salon: str, active_only: bool = False) -> dict[str, dict]:
        return self.salon(salon).employee_infos(active_only)

    def save_employee(self, salon: str, data: dict, must_exist: bool) -> str:
        s = self.salon(salon)
        if not data.get("name", "").strip():
            raise ValueError("Employee name is required")
        if not data.get("type", {}).get("role"):
            raise ValueError("Choose a role")
        exists = any(k.lower() == data["name"].strip().lower() for k in s.employees)
        if must_exist and not exists:
            raise ValueError(f"{data['name']} does not exist in {salon} - use Save New")
        if not must_exist and exists:
            raise ValueError(f"{data['name']} already exists in {salon} - use Update")
        return s.upsert_employee(data)

    def add_default_employee(self, salon: str, name: str) -> str:
        return self.salon(salon).add_default_employee(name)

    def remove_employees(self, salon: str, names: list[str]) -> None:
        for n in names:
            self.salon(salon).remove_employee(n)

    def set_employee_active(self, salon: str, name: str, active: bool) -> None:
        self.salon(salon).employees[name].active = active

    # ============================================================ sales data
    def latest_dates(self, kind: str) -> dict[str, str]:
        return {n: self.repo.latest_date(n, kind) or "none" for n in self.salon_names()}

    async def scrape_sales(self, salon: str, start: str, end: str, kind: str) -> None:
        """Download from Zota -> parse -> merge into JSON -> delete xlsx."""
        start, end = check_range(start, end)
        s = self.salon(salon)
        for c_start, c_end in split_range(start, end):
            log.info("%s: downloading %s sales %s - %s", salon, kind, c_start, c_end)
            target = config.DOWNLOAD_DIR / salon / f"{salon[0]}{kind}_{c_start.replace('/', '.')}.xlsx"
            if salon == 'upscale':
                path = await self.scraper.download_employee_sales(salon, s.username, s.password, c_start, c_end, target)
            else:
                path = await self.scraper.download_employee_sales_galaxy(salon, s.username, s.password, c_start, c_end, target)
            self.import_sales_file(salon, path, kind)
            path.unlink(missing_ok=True)

    def import_sales_file(self, salon: str, path: Path, kind: str) -> int:
        self.salon(salon)
        data = parse_sales_xlsx(path, kind)
        if not data:
            raise ValueError(f"No sales rows found in {Path(path).name} - is it the Employee Sales export?")
        self.repo.merge(salon, kind, data)
        days = sum(len(d) for d in data.values())
        log.info("%s: imported %d days of %s sales", salon, days, kind)
        return days

    # ============================================================ payroll
    def payroll(self, salon: str, start: str, end: str, guarantee: bool, booth) -> PayrollResult:
        """Always recalculates from JSON so late sales updates are picked up (same as old app)."""
        start, end = check_range(start, end)
        s = self.salon(salon)
        week = self.repo.get_range(salon, start, end, "regular")
        modified = self.repo.get_range(salon, start, end, "modified")
        result = s.calculate_payroll(week, modified, guarantee, booth)
        self.last_payroll[salon] = result
        for w in result.warnings:
            log.warning(w)
        return result

    def employee_status(self, salon: str) -> dict[str, dict]:
        return self.salon(salon).statuses()

    def export_payroll(self, salon: str, start: str, end: str) -> Path:
        """Call payroll() first. Writes HTML slips and appends to <year>.xlsx sheet '<x>.salary'."""
        s = self.salon(salon)
        slips = s.printable_slips()
        if not slips:
            raise ValueError(f"{salon}: nothing to export - calculate payroll first or no sales in range")
        html = write_payroll_html(config.PAYROLL_DIR / f"{start.replace('/', '.')}.{salon}.html", salon, slips)
        rows = build_1099_rows(s, start, end)
        book = config.PAYROLL_DIR / f"{start[-4:]}.xlsx"
        try:
            append_rows_to_book(book, f"{salon[0].lower()}.salary", rows)
        except PermissionError:
            raise RuntimeError(f"{book.name} is open in Excel - close it and export again")
        log.info("%s: exported %s and %d rows to %s", salon, html.name, len(rows), book.name)
        return html

    # ============================================================ reports
    def report_series(self, salon: str, start: str, end: str, freq: str, compare_years: bool):
        """
        Returns (x_labels, {series_name: [values]}) for the chart.
        freq: Daily | Weekly | Monthly | Yearly. compare_years overlays each year (old graphCompare).
        """
        start, end = check_range(start, end)
        rule = {"daily": "D", "weekly": "W-SUN", "monthly": "MS", "yearly": "YS"}[freq.lower()]
        names = self.resolve_salons(salon)
        frames = {}
        for n in names:
            days = self.repo.get_range(n, start, end, "regular")
            totals = {d: sum((v.get("sales") or 0) for v in emps.values()) for d, emps in days.items()}
            idx = pd.date_range(start, end, freq="D")
            frames[n] = pd.Series(totals, dtype=float).reindex(idx, fill_value=0.0)

        if not compare_years:
            df = pd.DataFrame(frames).resample(rule).sum()
            label = {"D": "%m/%d/%y", "W-SUN": "%m/%d/%y", "MS": "%b %Y", "YS": "%Y"}[rule]
            return [d.strftime(label) for d in df.index], {c: df[c].round(2).tolist() for c in df}

        if len(names) != 1:
            raise ValueError("Self-comparison works on one salon, not 'all'")
        series = frames[names[0]]
        key_fn = {"D": lambda d: d.strftime("%m/%d"), "W-SUN": lambda d: f"W{d.isocalendar().week:02d}",
                  "MS": lambda d: d.strftime("%b"), "YS": lambda d: "Year"}[rule]
        by_year = {}
        for year, chunk in series.groupby(series.index.year):
            agg = chunk.resample(rule).sum() if rule != "D" else chunk
            by_year[str(year)] = {key_fn(d): round(v, 2) for d, v in agg.items()}
        labels = sorted({k for y in by_year.values() for k in y},
                        key=lambda k: list(pd.date_range("2024-01-01", "2024-12-31").strftime("%m/%d")).index(k)
                        if rule == "D" else (dt.datetime.strptime(k, "%b").month if rule == "MS" else k))
        return labels, {y: [vals.get(k, 0) for k in labels] for y, vals in by_year.items()}
