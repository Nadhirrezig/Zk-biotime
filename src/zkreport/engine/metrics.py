"""Per shift-day metrics, all thresholds from Rules."""
from __future__ import annotations

from datetime import datetime, timedelta

from .models import LateMode, Rules


def _minutes(delta: timedelta) -> int:
    return int(delta.total_seconds() // 60)


def late_minutes(arrival: datetime | None, start: datetime, rules: Rules) -> int:
    if arrival is None:
        return 0
    threshold = start + timedelta(minutes=rules.late_tolerance_min)
    if arrival <= threshold:
        return 0
    base = threshold if rules.late_mode is LateMode.AFTER_TOLERANCE else start
    return _minutes(arrival - base)


def early_leave_minutes(departure: datetime | None, end: datetime, rules: Rules) -> int:
    if departure is None:
        return 0
    threshold = end - timedelta(minutes=rules.early_leave_tolerance_min)
    if departure >= threshold:
        return 0
    base = threshold if rules.late_mode is LateMode.AFTER_TOLERANCE else end
    return _minutes(base - departure)


def worked_minutes(arrival: datetime | None, departure: datetime | None) -> int:
    if arrival is None or departure is None or departure <= arrival:
        return 0
    return _minutes(departure - arrival)


def overtime_minutes(departure: datetime | None, end: datetime, rules: Rules) -> int:
    if departure is None or departure <= end:
        return 0
    extra = _minutes(departure - end)
    return extra if extra >= rules.overtime_threshold_min else 0
