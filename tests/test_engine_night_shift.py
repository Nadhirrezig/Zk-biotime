"""Rotating Production 3x8 (06-14, 14-22, 22-06) and fixed overnight shifts."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from conftest import ALL_DAYS, TZ, make_rules, production_config
from zkreport.engine import compute, summarize
from zkreport.engine.models import (
    EngineConfig,
    Employee,
    Missing,
    Punch,
    SchedulePeriod,
    ShiftDef,
    Status,
)

TUNIS = ZoneInfo("Africa/Tunis")
SHANGHAI = ZoneInfo("Asia/Shanghai")
WORKER = Employee("247", "Hassen", "Marouani", "Production")


def tunis(y, mo, d, h, mi):
    # Store as +08 like the DB does, to exercise the conversion.
    return datetime(y, mo, d, h, mi, tzinfo=TUNIS).astimezone(SHANGHAI)


def rows_for(results, day):
    return [r for r in results if r.day == day]


def hm(dt):
    return dt.astimezone(TUNIS).strftime("%H:%M") if dt else None


def test_night_shift_attached_to_arrival_date():
    punches = [Punch("247", tunis(2026, 10, 27, 21, 48)), Punch("247", tunis(2026, 10, 28, 5, 55))]
    results = compute([WORKER], punches, production_config(), date(2026, 10, 27), date(2026, 10, 28))
    (oct27,) = rows_for(results, date(2026, 10, 27))
    assert oct27.status is Status.COMPLETE
    assert oct27.shift_code == "PRD_N"
    assert (hm(oct27.arrival), hm(oct27.departure)) == ("21:48", "05:55")
    assert oct27.departure.astimezone(TUNIS).date() == date(2026, 10, 28)
    (oct28,) = rows_for(results, date(2026, 10, 28))
    assert oct28.status is Status.ABSENT


def test_rotating_auto_picks_nearest_shift():
    punches = [
        Punch("247", tunis(2026, 10, 20, 5, 50)), Punch("247", tunis(2026, 10, 20, 13, 58)),
        Punch("247", tunis(2026, 10, 21, 13, 50)), Punch("247", tunis(2026, 10, 21, 22, 5)),
        Punch("247", tunis(2026, 10, 22, 21, 40)), Punch("247", tunis(2026, 10, 23, 6, 2)),
    ]
    results = compute([WORKER], punches, production_config(), date(2026, 10, 20), date(2026, 10, 23))
    codes = {r.day: (r.shift_code, r.status) for r in results}
    assert codes[date(2026, 10, 20)] == ("PRD_M", Status.COMPLETE)
    assert codes[date(2026, 10, 21)] == ("PRD_A", Status.COMPLETE)
    assert codes[date(2026, 10, 22)] == ("PRD_N", Status.COMPLETE)
    assert codes[date(2026, 10, 23)] == (None, Status.ABSENT)
    oct21 = rows_for(results, date(2026, 10, 21))[0]
    assert (hm(oct21.arrival), hm(oct21.departure)) == ("13:50", "22:05")


def test_lone_punch_at_shift_change_is_night_departure():
    punches = [Punch("247", tunis(2026, 10, 28, 5, 55))]
    results = compute([WORKER], punches, production_config(), date(2026, 10, 27), date(2026, 10, 28))
    (oct27,) = rows_for(results, date(2026, 10, 27))
    assert oct27.status is Status.SINGLE_PUNCH
    assert oct27.missing is Missing.ARRIVAL
    assert oct27.shift_code == "PRD_N"


def test_lone_punch_tie_without_context_resolves_to_departure():
    # 21:42 is 18 min from both the 14-22 end and the 22-06 start: no history -> departure.
    punches = [Punch("247", tunis(2026, 10, 25, 21, 42))]
    results = compute([WORKER], punches, production_config(), date(2026, 10, 25), date(2026, 10, 25))
    (row,) = results
    assert row.status is Status.SINGLE_PUNCH
    assert row.missing is Missing.ARRIVAL
    assert row.shift_code == "PRD_A"


def test_lone_punch_tie_uses_neighbouring_shift_night():
    punches = [
        Punch("247", tunis(2026, 10, 24, 21, 50)), Punch("247", tunis(2026, 10, 25, 5, 56)),
        Punch("247", tunis(2026, 10, 25, 21, 42)),  # forgot the departure
        Punch("247", tunis(2026, 10, 26, 21, 47)), Punch("247", tunis(2026, 10, 27, 5, 58)),
    ]
    results = compute([WORKER], punches, production_config(), date(2026, 10, 24), date(2026, 10, 26))
    (oct25,) = rows_for(results, date(2026, 10, 25))
    assert (oct25.shift_code, oct25.status, oct25.missing) == (
        "PRD_N", Status.SINGLE_PUNCH, Missing.DEPARTURE,
    )
    assert [r.status for r in results].count(Status.COMPLETE) == 2


def test_lone_punch_tie_uses_neighbouring_shift_morning():
    punches = [
        Punch("247", tunis(2026, 10, 27, 5, 52)), Punch("247", tunis(2026, 10, 27, 13, 55)),
        Punch("247", tunis(2026, 10, 28, 5, 50)),  # forgot the departure
        Punch("247", tunis(2026, 10, 29, 5, 49)), Punch("247", tunis(2026, 10, 29, 13, 57)),
    ]
    results = compute([WORKER], punches, production_config(), date(2026, 10, 27), date(2026, 10, 29))
    (oct28,) = rows_for(results, date(2026, 10, 28))
    assert (oct28.shift_code, oct28.missing) == ("PRD_M", Missing.DEPARTURE)
    assert rows_for(results, date(2026, 10, 27))[0].status is Status.COMPLETE


def test_fixed_overnight_guard_shift():
    config = EngineConfig(
        timezone=TZ,
        rules=make_rules(),
        shifts=(ShiftDef("GRD", "Gardiennage", time(18, 0), time(6, 0)),),
        periods=(SchedulePeriod("Gardiennage", ("GRD",), ALL_DAYS),),
    )
    guard = Employee("227", "Youssef", "Kouki", "Gardiennage")
    punches = [Punch("227", tunis(2026, 10, 20, 17, 59)), Punch("227", tunis(2026, 10, 21, 5, 56))]
    # Ali-like lone morning punch the next day.
    punches.append(Punch("227", tunis(2026, 10, 22, 5, 58)))
    results = compute([guard], punches, config, date(2026, 10, 20), date(2026, 10, 21))
    oct20, oct21 = results
    assert (oct20.status, hm(oct20.arrival), hm(oct20.departure)) == (Status.COMPLETE, "17:59", "05:56")
    assert (oct21.status, oct21.missing) == (Status.SINGLE_PUNCH, Missing.ARRIVAL)


def test_summary_counts():
    other = Employee("310", "Aziz", "Manouba", "Production")
    punches = [
        Punch("247", tunis(2026, 10, 20, 6, 30)), Punch("247", tunis(2026, 10, 20, 14, 0)),
    ]
    results = compute([WORKER, other], punches, production_config(), date(2026, 10, 20), date(2026, 10, 20))
    counts = summarize(results)
    assert counts.employees == 2
    assert counts.present == 1
    assert counts.complete == 1
    assert counts.absent == 1
    assert counts.single_punch == 0


def test_excluded_and_resigned_employees_are_skipped():
    admin = Employee("1", "Admin", "", "Production")
    gone = Employee("999", "Ex", "Employé", "Production", resign_date=date(2026, 10, 1))
    config = production_config()
    config = EngineConfig(
        timezone=config.timezone, rules=config.rules, shifts=config.shifts,
        periods=config.periods, excluded_emp_codes=frozenset({"1"}),
    )
    results = compute([admin, gone, WORKER], [], config, date(2026, 10, 20), date(2026, 10, 20))
    assert [r.emp_code for r in results] == ["247"]


def test_unscheduled_punches_are_reported():
    nobody = Employee("400", "Sans", "Planning", "Inconnu")
    start = tunis(2026, 10, 20, 9, 0)
    punches = [Punch("400", start), Punch("400", start + timedelta(hours=8))]
    (row,) = compute([nobody], punches, production_config(), date(2026, 10, 20), date(2026, 10, 20))
    assert row.unscheduled
    assert row.status is Status.COMPLETE
    assert row.punch_count == 2
