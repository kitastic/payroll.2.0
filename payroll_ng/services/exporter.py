"""Writes the printable HTML payroll and appends rows to the yearly 1099 workbook."""
from __future__ import annotations

import math
import re
from pathlib import Path

import openpyxl

from config import STATIC_DIR

HTML_HEAD = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
  body {{ font-family: 'Courier New', monospace; font-size: 13px; }}
  .slip {{ white-space: pre; margin-bottom: 2em; }}
  @media print {{ .pagebreak {{ clear: both; page-break-before: always; }} }}
</style></head><body>
"""


def write_payroll_html(path: Path, salon: str, printouts: dict[str, str]) -> Path:
    logo = STATIC_DIR / f"{salon[0].lower()}logo.png"
    logo_tag = f'<img src="/static/{logo.name}" style="width:100px"><br>' if logo.is_file() else ""
    parts = [f'{logo_tag}<div class="slip">{text}</div>' for text in printouts.values()]
    html = HTML_HEAD.format(title=path.stem) + '<div class="pagebreak"></div>'.join(parts) + "</body></html>"
    path.write_text(html, encoding="utf-8")
    return path


def build_1099_rows(salon_obj, start: str, end: str) -> list[list]:
    """Same columns as before: start, end, name, cash, check, checkdeal, booth."""
    rows = []
    for key, emp in salon_obj.payable_employees().items():
        if not (emp.printchecks or emp.role.lower() == "cash"):
            continue
        x = emp.xlreport
        name = emp.checkName if len(emp.checkName) > 1 else re.search(r"^[^(]+", key).group(0).strip().upper()
        rows.append([start, end, name, math.ceil(x["bcash"]), math.ceil(x["bcheck"]),
                     math.ceil(x["checkdeal"]), x["booth"]])
    return rows


def append_rows_to_book(path: Path, sheet: str, rows: list[list]) -> None:
    """Appends after the last non-empty row in column A. Creates the book/sheet if missing."""
    if path.is_file():
        wb = openpyxl.load_workbook(path)
    else:
        wb = openpyxl.Workbook()
        wb.active.title = sheet
        wb[sheet].append(["Start", "End", "Name", "Cash", "Check", "Check Deal", "Booth"])
    ws = wb[sheet] if sheet in wb.sheetnames else wb.create_sheet(sheet)
    last = 0
    for r in range(ws.max_row, 0, -1):
        if ws.cell(r, 1).value not in (None, ""):
            last = r
            break
    for i, row in enumerate(rows, start=1):
        for c, value in enumerate(row, start=1):
            ws.cell(last + i, c, value)
    wb.save(path)
