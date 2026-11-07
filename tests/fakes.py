"""In-memory stand-in for ZkRepository, fed from the Rahma fixture plus synthetic staff."""
from contextlib import contextmanager
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from conftest import FIXTURES
from zkreport.engine.models import Employee, Punch

import csv

TUNIS = ZoneInfo("Africa/Tunis")

EMPLOYEES = [
    Employee("1", "Admin", "", "Production"),
    Employee("302", "Rahma", "Achour", "Administration"),
    Employee("247", "Hassen", "Marouani", "Production"),
    Employee("215", "Ridha", "Slaimi", "Production"),
    Employee("227", "Youssef", "Kouki", "Gardiennage"),
    Employee("155", "", "", "Production"),
]


def _t(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=TUNIS)


def synthetic_punches():
    out = []
    for day in range(20, 31):
        out.append(Punch("247", _t(2026, 9, day, 5, 52)))     # morning 06-14
        out.append(Punch("247", _t(2026, 9, day, 13, 56)))
        out.append(Punch("215", _t(2026, 9, day, 21, 48)))    # night 22-06
        if day != 24:
            out.append(Punch("215", _t(2026, 9, day, 21, 48) + timedelta(hours=8, minutes=7)))
        out.append(Punch("227", _t(2026, 9, day, 17, 59)))    # guard 18-06
        out.append(Punch("227", _t(2026, 9, day, 17, 59) + timedelta(hours=11, minutes=57)))
    out.append(Punch("1", _t(2026, 9, 24, 10, 0)))            # excluded test account
    return out


def rahma_punches():
    with (FIXTURES / "rahma_punches.csv").open(encoding="utf-8") as fh:
        return [Punch(r["emp_code"], datetime.fromisoformat(r["punch_time"]))
                for r in csv.DictReader(fh)]


class FakeRepository:
    def __init__(self, employees=None, punches=None):
        self._employees = list(EMPLOYEES if employees is None else employees)
        self._punches = list(rahma_punches() + synthetic_punches() if punches is None else punches)
        self.calls = []

    def employees(self):
        self.calls.append("employees")
        return list(self._employees)

    def punches(self, start, end, emp_code=None):
        self.calls.append(("punches", start, end))
        return [p for p in self._punches if start <= p.time < end
                and (emp_code is None or p.emp_code == emp_code)]

    def last_punch_time(self):
        return max(p.time for p in self._punches) if self._punches else None

    def server_info(self):
        return {"version": "fake", "timezone": "Africa/Tunis", "read_only": "on",
                "employees": len(self._employees), "punches": len(self._punches)}


def fake_factory(repo=None):
    repo = repo or FakeRepository()

    @contextmanager
    def factory():
        yield repo

    return factory
