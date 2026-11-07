"""Engine data types. Pure Python: every rule value comes from the caller's config."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from enum import Enum


class Status(str, Enum):
    COMPLETE = "complete"          # arrival and departure
    SINGLE_PUNCH = "single_punch"  # one punch (or one burst) only
    ABSENT = "absent"              # scheduled, no punch, no leave, no holiday
    LEAVE = "leave"
    HOLIDAY = "holiday"
    REST = "rest"                  # no schedule for that day


class Missing(str, Enum):
    NONE = "none"
    ARRIVAL = "arrival"
    DEPARTURE = "departure"


class LateMode(str, Enum):
    AFTER_TOLERANCE = "after_tolerance"  # minutes counted from start + tolerance
    FROM_START = "from_start"            # minutes counted from start once past tolerance


@dataclass(frozen=True)
class Punch:
    emp_code: str
    time: datetime  # timezone-aware


@dataclass(frozen=True)
class Employee:
    emp_code: str
    first_name: str = ""
    last_name: str = ""
    department: str = ""
    resign_date: date | None = None

    @property
    def full_name(self) -> str:
        return f"{self.first_name or ''} {self.last_name or ''}".strip()


@dataclass(frozen=True)
class ShiftDef:
    code: str
    name: str
    start: time
    end: time

    @property
    def crosses_midnight(self) -> bool:
        return self.end <= self.start


MonthDay = tuple[int, int]


@dataclass(frozen=True)
class SchedulePeriod:
    """Which shift(s) a department works on given weekdays, optionally within a yearly
    month-day range. Several shift codes = rotating, the engine picks per punch."""

    department: str
    shift_codes: tuple[str, ...]
    weekdays: frozenset[int]  # 0 = Monday ... 6 = Sunday
    valid_from: MonthDay | None = None
    valid_to: MonthDay | None = None
    priority: int = 0
    name: str = ""

    def applies(self, day: date) -> bool:
        if day.weekday() not in self.weekdays:
            return False
        if self.valid_from is None or self.valid_to is None:
            return True
        md = (day.month, day.day)
        if self.valid_from <= self.valid_to:
            return self.valid_from <= md <= self.valid_to
        return md >= self.valid_from or md <= self.valid_to  # wraps over new year


@dataclass(frozen=True)
class Holiday:
    day: date
    name: str
    recurring: bool = False  # same month/day every year

    def matches(self, day: date) -> bool:
        if self.recurring:
            return (self.day.month, self.day.day) == (day.month, day.day)
        return self.day == day


@dataclass(frozen=True)
class Leave:
    emp_code: str
    date_from: date
    date_to: date
    reason: str = ""


@dataclass(frozen=True)
class Rules:
    duplicate_window_min: int
    late_tolerance_min: int
    early_leave_tolerance_min: int
    late_mode: LateMode
    window_before_start_min: int
    window_after_end_min: int
    overtime_threshold_min: int


@dataclass(frozen=True)
class EngineConfig:
    timezone: str
    rules: Rules
    shifts: tuple[ShiftDef, ...]
    periods: tuple[SchedulePeriod, ...]
    holidays: tuple[Holiday, ...] = ()
    excluded_emp_codes: frozenset[str] = frozenset()


@dataclass(frozen=True)
class DayResult:
    emp_code: str
    name: str
    department: str
    day: date                       # shift-day: the date the shift starts
    status: Status
    missing: Missing = Missing.NONE
    shift_code: str | None = None
    shift_name: str | None = None
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    arrival: datetime | None = None
    departure: datetime | None = None
    punches: tuple[datetime, ...] = ()
    late_min: int = 0
    early_leave_min: int = 0
    worked_min: int = 0
    overtime_min: int = 0
    holiday_name: str | None = None
    unscheduled: bool = False       # punches outside every scheduled window

    @property
    def punch_count(self) -> int:
        return len(self.punches)

    @property
    def is_late(self) -> bool:
        return self.late_min > 0

    @property
    def is_present(self) -> bool:
        return self.status in (Status.COMPLETE, Status.SINGLE_PUNCH)
