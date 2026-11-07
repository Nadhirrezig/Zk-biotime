"""Resolve what is expected of an employee on a given date."""
from __future__ import annotations

from datetime import date

from .models import Holiday, Leave, SchedulePeriod


def _norm(name: str) -> str:
    return (name or "").strip().casefold()


def resolve_period(
    periods: tuple[SchedulePeriod, ...], department: str, day: date
) -> SchedulePeriod | None:
    """Highest-priority period of the department that applies on `day`; None = rest day.
    On equal priority the first defined period wins."""
    dept = _norm(department)
    best: SchedulePeriod | None = None
    for period in periods:
        if _norm(period.department) != dept or not period.applies(day):
            continue
        if best is None or period.priority > best.priority:
            best = period
    return best


def holiday_for(holidays: tuple[Holiday, ...], day: date) -> Holiday | None:
    for holiday in holidays:
        if holiday.matches(day):
            return holiday
    return None


def leave_for(leaves, emp_code: str, day: date) -> Leave | None:
    for leave in leaves:
        if leave.emp_code == emp_code and leave.date_from <= day <= leave.date_to:
            return leave
    return None
