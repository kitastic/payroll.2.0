"""Turns the Zota 'Employee Sales' Excel export into {year: {"mm/dd/yyyy": {emp: {...}}}}."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import openpyxl

from config import DATE_FMT


def parse_sales_xlsx(path: str | Path, kind: str = "regular") -> dict[int, dict]:
    """
    Layout (unchanged from Salon.readSalesXltoJson):
      - a row whose first cell is a datetime starts a new day
      - a row with column B == 'S' is a tech: A=name, E=sales, K=tips, L=commission
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    result: dict[int, dict] = {}
    day: dt.datetime | None = None
    for row in ws.iter_rows(values_only=True):
        if not row or row[0] in (None, ""):
            continue
        if isinstance(row[0], dt.datetime):
            day = row[0]
            continue
        if day is None or len(row) < 11 or row[1] != "S":
            continue
        entry = {"sales": row[4] or 0, "tips": row[10] or 0}
        if kind == "modified":
            entry["commission"] = (row[11] if len(row) > 11 else 0) or 0
        name = " ".join(str(row[0]).split())          # trims stray spaces from Zota names
        result.setdefault(day.year, {}).setdefault(day.strftime(DATE_FMT), {})[name] = entry
    wb.close()
    return result
