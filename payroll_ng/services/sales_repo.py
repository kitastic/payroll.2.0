"""
Read/write the yearly sales JSON files. Same file names and layout as the old app:
    <db>/<salon>Sales<year>.json          {"mm/dd/yyyy": {"Emp Name": {"sales": x, "tips": y}}}
    <db>/<salon>ModifiedSales<year>.json  {"mm/dd/yyyy": {"Emp Name": {"sales", "tips", "commission"}}}
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from config import DATE_FMT


class SalesRepo:
    def __init__(self, db_dir: Path):
        self.db_dir = Path(db_dir)

    def _file(self, salon: str, year: int, kind: str) -> Path:
        middle = "Sales" if kind == "regular" else "ModifiedSales"
        return self.db_dir / f"{salon}{middle}{year}.json"

    def _load(self, path: Path) -> dict:
        if not path.is_file() or path.stat().st_size < 3:
            return {}
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data or {}

    def merge(self, salon: str, kind: str, by_year: dict[int, dict]) -> None:
        """New data wins over old for the same day (same as old `old | new`)."""
        for year, days in by_year.items():
            path = self._file(salon, year, kind)
            merged = self._load(path) | days
            ordered = dict(sorted(merged.items(), key=lambda kv: dt.datetime.strptime(kv[0], DATE_FMT)))
            with open(path, "w", encoding="utf-8") as f:
                json.dump(ordered, f, indent=4)

    def get_range(self, salon: str, start: str, end: str, kind: str) -> dict[dt.datetime, dict]:
        s, e = dt.datetime.strptime(start, DATE_FMT), dt.datetime.strptime(end, DATE_FMT)
        out = {}
        for year in range(s.year, e.year + 1):
            for key, emps in self._load(self._file(salon, year, kind)).items():
                day = dt.datetime.strptime(key, DATE_FMT)
                if s <= day <= e:
                    out[day] = emps
        return dict(sorted(out.items()))

    def latest_date(self, salon: str, kind: str) -> str | None:
        """Latest recorded day, looking back through years that have files."""
        year = dt.date.today().year
        for y in range(year, year - 5, -1):
            data = self._load(self._file(salon, y, kind))
            if data:
                return max(data, key=lambda k: dt.datetime.strptime(k, DATE_FMT))
        return None
