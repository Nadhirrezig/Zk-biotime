"""Rahma (emp_code 302, Administration) reference cases, Tunis time."""
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from conftest import TUNISIA_HOLIDAYS, admin_config, make_rules
from zkreport.engine import compute
from zkreport.engine.models import LateMode, Leave, Missing, Punch, Status

TUNIS = ZoneInfo("Africa/Tunis")
SHANGHAI = ZoneInfo("Asia/Shanghai")


def one_day(results, day):
    rows = [r for r in results if r.day == day]
    assert len(rows) == 1, rows
    return rows[0]


def hm(dt):
    return dt.astimezone(TUNIS).strftime("%H:%M") if dt else None


def test_stored_plus08_punch_is_departure_of_previous_tunis_day(rahma):
    # 2026-09-01 08:40 Tunis arrival, then the punch stored as 2026-09-02 00:03+08.
    punches = [
        Punch("302", datetime(2026, 9, 1, 15, 40, tzinfo=SHANGHAI)),
        Punch("302", datetime(2026, 9, 2, 0, 3, tzinfo=SHANGHAI)),
    ]
    stored = punches[1].time.astimezone(TUNIS)
    assert (stored.date(), stored.time()) == (date(2026, 9, 1), time(17, 3))

    results = compute([rahma], punches, admin_config(), date(2026, 9, 1), date(2026, 9, 2))
    sep1 = one_day(results, date(2026, 9, 1))
    assert sep1.status is Status.COMPLETE
    assert (hm(sep1.arrival), hm(sep1.departure)) == ("08:40", "17:03")
    sep2 = one_day(results, date(2026, 9, 2))
    assert sep2.status is Status.ABSENT
    assert sep2.punches == ()


def test_full_fixture_sep_1_and_2(rahma, rahma_punches):
    results = compute([rahma], rahma_punches, admin_config(), date(2026, 9, 1), date(2026, 9, 2))
    sep1 = one_day(results, date(2026, 9, 1))
    sep2 = one_day(results, date(2026, 9, 2))
    assert (hm(sep1.arrival), hm(sep1.departure)) == ("08:40", "17:03")
    assert (hm(sep2.arrival), hm(sep2.departure)) == ("08:26", "16:23")
    assert all(p.astimezone(TUNIS).date() == date(2026, 9, 2) for p in sep2.punches)


@pytest.mark.parametrize("window", [5, 10])
def test_jul_16_duplicates_collapse_to_first_and_last(rahma, rahma_punches, window):
    config = admin_config(rules=make_rules(duplicate_window_min=window))
    day = date(2026, 7, 16)
    row = one_day(compute([rahma], rahma_punches, config, day, day), day)
    assert row.status is Status.COMPLETE
    assert (hm(row.arrival), hm(row.departure)) == ("10:20", "14:45")
    assert row.punch_count == 9
    assert row.worked_min == 4 * 60 + 25


def test_sep_24_single_punch_is_missing_arrival(rahma, rahma_punches):
    day = date(2026, 9, 24)
    row = one_day(compute([rahma], rahma_punches, admin_config(), day, day), day)
    assert row.status is Status.SINGLE_PUNCH
    assert row.missing is Missing.ARRIVAL
    assert row.arrival is None
    assert hm(row.departure) == "16:52"


@pytest.mark.parametrize("day", [date(2026, 7, 25), date(2026, 10, 15)])
def test_public_holidays_without_punches(rahma, rahma_punches, day):
    config = admin_config(holidays=TUNISIA_HOLIDAYS)
    row = one_day(compute([rahma], rahma_punches, config, day, day), day)
    assert row.status is Status.HOLIDAY
    assert row.holiday_name


def test_holiday_not_configured_is_absent(rahma, rahma_punches):
    day = date(2026, 10, 15)
    row = one_day(compute([rahma], rahma_punches, admin_config(), day, day), day)
    assert row.status is Status.ABSENT


AUG_LEAVE = [date(2026, 8, d) for d in range(10, 23)]
AUG_WORKDAYS = [d for d in AUG_LEAVE if d.weekday() != 6]


def test_aug_10_22_absent_without_leave(rahma, rahma_punches):
    results = compute([rahma], rahma_punches, admin_config(), AUG_LEAVE[0], AUG_LEAVE[-1])
    for d in AUG_WORKDAYS:
        assert one_day(results, d).status is Status.ABSENT, d
    assert one_day(results, date(2026, 8, 16)).status is Status.REST


def test_aug_10_22_leave_once_entered(rahma, rahma_punches):
    leave = [Leave("302", date(2026, 8, 10), date(2026, 8, 22))]
    results = compute(
        [rahma], rahma_punches, admin_config(), AUG_LEAVE[0], AUG_LEAVE[-1], leaves=leave
    )
    for d in AUG_WORKDAYS:
        assert one_day(results, d).status is Status.LEAVE, d
    assert one_day(results, date(2026, 8, 16)).status is Status.REST


@pytest.mark.parametrize(
    "start, mode, expected",
    [
        ("08:00", LateMode.AFTER_TOLERANCE, 173),  # 11:03 - 08:10
        ("08:30", LateMode.AFTER_TOLERANCE, 143),  # 11:03 - 08:40
        ("08:00", LateMode.FROM_START, 183),       # 11:03 - 08:00
        ("08:30", LateMode.FROM_START, 153),       # 11:03 - 08:30
    ],
)
def test_jul_17_late_arrival(rahma, rahma_punches, start, mode, expected):
    config = admin_config(start=start, rules=make_rules(late_mode=mode, late_tolerance_min=10))
    day = date(2026, 7, 17)
    row = one_day(compute([rahma], rahma_punches, config, day, day), day)
    assert hm(row.arrival) == "11:03"
    assert row.is_late
    assert row.late_min == expected


def test_arrival_within_tolerance_is_not_late(rahma, rahma_punches):
    # 2026-07-29 arrival 08:01, tolerance 10 -> on time.
    day = date(2026, 7, 29)
    row = one_day(compute([rahma], rahma_punches, admin_config(), day, day), day)
    assert hm(row.arrival) == "08:01"
    assert row.late_min == 0 and not row.is_late


def test_sunday_is_rest_for_administration(rahma, rahma_punches):
    day = date(2026, 9, 6)  # Sunday
    row = one_day(compute([rahma], rahma_punches, admin_config(), day, day), day)
    assert row.status is Status.REST


def test_saturday_uses_saturday_shift(rahma, rahma_punches):
    day = date(2026, 7, 18)  # 08:22, 08:30, 08:32, 13:04
    row = one_day(compute([rahma], rahma_punches, admin_config(), day, day), day)
    assert row.shift_code == "ADM_SAT"
    assert (hm(row.arrival), hm(row.departure)) == ("08:22", "13:04")
    assert row.early_leave_min == 0


def test_whole_dataset_one_row_per_day(rahma, rahma_punches):
    start, end = date(2026, 7, 16), date(2026, 10, 30)
    results = compute([rahma], rahma_punches, admin_config(holidays=TUNISIA_HOLIDAYS), start, end)
    assert len(results) == (end - start).days + 1
    assigned = sum(r.punch_count for r in results)
    assert assigned == len(rahma_punches)
    assert not any(r.unscheduled for r in results)
