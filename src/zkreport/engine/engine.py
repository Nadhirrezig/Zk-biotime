"""Entry point: punches + config -> one DayResult per employee and shift-day."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable
from zoneinfo import ZoneInfo

from . import metrics
from .models import DayResult, EngineConfig, Employee, Leave, Missing, Punch, Status
from .pairing import Assignment, Cluster, build_instance, pair_punches
from .scheduling import holiday_for, leave_for, resolve_period


def _days(start: date, end: date):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def compute(
    employees: Iterable[Employee],
    punches: Iterable[Punch],
    config: EngineConfig,
    date_from: date,
    date_to: date,
    leaves: Iterable[Leave] = (),
) -> list[DayResult]:
    """Punches must cover [date_from - 1 day, date_to + 1 day] so that overnight shifts
    on the edges are paired correctly."""
    tz = ZoneInfo(config.timezone)
    rules = config.rules
    shifts = {s.code: s for s in config.shifts}
    leaves = tuple(leaves)

    by_emp: dict[str, list] = defaultdict(list)
    for punch in punches:
        by_emp[punch.emp_code].append(punch.time.astimezone(tz))

    results: list[DayResult] = []
    for emp in employees:
        if emp.emp_code in config.excluded_emp_codes:
            continue
        instances = []
        for day in _days(date_from - timedelta(days=1), date_to + timedelta(days=1)):
            period = resolve_period(config.periods, emp.department, day)
            if period is None:
                continue
            for code in period.shift_codes:
                if code in shifts:
                    instances.append(build_instance(day, shifts[code], tz, rules))

        assignments, orphans = pair_punches(by_emp.get(emp.emp_code, []), instances, rules)
        by_day: dict[date, list[Assignment]] = defaultdict(list)
        for a in assignments:
            by_day[a.instance.day].append(a)
        orphans_by_day: dict[date, list[Cluster]] = defaultdict(list)
        for cluster in orphans:
            orphans_by_day[cluster.first.date()].append(cluster)

        for day in _days(date_from, date_to):
            if emp.resign_date is not None and day > emp.resign_date:
                continue
            holiday = holiday_for(config.holidays, day)
            holiday_name = holiday.name if holiday else None
            for a in sorted(by_day.get(day, []), key=lambda a: a.instance.start):
                results.append(_from_assignment(emp, a, rules, holiday_name))
            if day in orphans_by_day:
                results.append(_unscheduled(emp, day, orphans_by_day[day], holiday_name))
            if day in by_day or day in orphans_by_day:
                continue
            period = resolve_period(config.periods, emp.department, day)
            if holiday:
                status = Status.HOLIDAY
            elif period is None:
                status = Status.REST
            elif leave_for(leaves, emp.emp_code, day):
                status = Status.LEAVE
            else:
                status = Status.ABSENT
            shift = None
            if period is not None and len(period.shift_codes) == 1:
                shift = shifts.get(period.shift_codes[0])
            results.append(DayResult(
                emp_code=emp.emp_code, name=emp.full_name, department=emp.department,
                day=day, status=status,
                shift_code=shift.code if shift else None,
                shift_name=shift.name if shift else None,
                holiday_name=holiday_name,
            ))
    return results


def _from_assignment(emp: Employee, a: Assignment, rules, holiday_name) -> DayResult:
    inst = a.instance
    times = tuple(t for c in a.clusters for t in c.times)
    if a.arrival_missing:
        arrival, departure, missing = None, a.clusters[-1].last, Missing.ARRIVAL
    elif len(a.clusters) >= 2:
        arrival, departure, missing = a.clusters[0].first, a.clusters[-1].last, Missing.NONE
    else:
        arrival, departure, missing = a.clusters[0].first, None, Missing.DEPARTURE
    return DayResult(
        emp_code=emp.emp_code, name=emp.full_name, department=emp.department,
        day=inst.day,
        status=Status.COMPLETE if missing is Missing.NONE else Status.SINGLE_PUNCH,
        missing=missing,
        shift_code=inst.shift.code, shift_name=inst.shift.name,
        scheduled_start=inst.start, scheduled_end=inst.end,
        arrival=arrival, departure=departure, punches=times,
        late_min=metrics.late_minutes(arrival, inst.start, rules),
        early_leave_min=metrics.early_leave_minutes(departure, inst.end, rules),
        worked_min=metrics.worked_minutes(arrival, departure),
        overtime_min=metrics.overtime_minutes(departure, inst.end, rules),
        holiday_name=holiday_name,
    )


def _unscheduled(emp: Employee, day: date, clusters: list[Cluster], holiday_name) -> DayResult:
    times = tuple(t for c in clusters for t in c.times)
    complete = len(clusters) >= 2
    arrival = clusters[0].first
    departure = clusters[-1].last if complete else None
    return DayResult(
        emp_code=emp.emp_code, name=emp.full_name, department=emp.department,
        day=day,
        status=Status.COMPLETE if complete else Status.SINGLE_PUNCH,
        missing=Missing.NONE if complete else Missing.DEPARTURE,
        arrival=arrival, departure=departure, punches=times,
        worked_min=metrics.worked_minutes(arrival, departure),
        holiday_name=holiday_name, unscheduled=True,
    )


@dataclass(frozen=True)
class Summary:
    employees: int
    present: int
    complete: int
    single_punch: int
    late: int
    absent: int
    leave: int
    holiday: int
    rest: int


def summarize(results: Iterable[DayResult]) -> Summary:
    """Distinct-employee counts (an employee with two shift rows counts once per bucket)."""
    buckets: dict[str, set[str]] = defaultdict(set)
    for r in results:
        buckets["all"].add(r.emp_code)
        buckets[r.status.value].add(r.emp_code)
        if r.is_present:
            buckets["present"].add(r.emp_code)
        if r.is_late:
            buckets["late"].add(r.emp_code)
    return Summary(
        employees=len(buckets["all"]),
        present=len(buckets["present"]),
        complete=len(buckets[Status.COMPLETE.value]),
        single_punch=len(buckets[Status.SINGLE_PUNCH.value]),
        late=len(buckets["late"]),
        absent=len(buckets[Status.ABSENT.value]),
        leave=len(buckets[Status.LEAVE.value]),
        holiday=len(buckets[Status.HOLIDAY.value]),
        rest=len(buckets[Status.REST.value]),
    )
