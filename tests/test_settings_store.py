"""SQLite settings store: seeding, round trips, validation."""
from datetime import date, time

import pytest

from zkreport.engine import compute
from zkreport.engine.models import Employee, Holiday, LateMode, SchedulePeriod, ShiftDef, Status
from zkreport.store.seed import DEFAULT_SETTINGS
from zkreport.store.settings_store import SettingsStore


@pytest.fixture
def store(tmp_path):
    s = SettingsStore(tmp_path / "settings.db")
    yield s
    s.close()


def test_seeded_defaults(store):
    assert store.all_settings() == DEFAULT_SETTINGS
    config = store.engine_config()
    assert config.timezone == "Africa/Tunis"
    assert config.rules.late_mode is LateMode.AFTER_TOLERANCE
    assert config.excluded_emp_codes == frozenset({"1"})
    assert {s.code for s in config.shifts} >= {"ADM", "PRD_N", "GARD"}
    assert {p.department for p in config.periods} == {"Administration", "Production", "Gardiennage"}
    assert any(h.name.startswith("Fête de la République") and h.recurring for h in config.holidays)


def test_seed_runs_once_and_user_edits_survive_reopen(tmp_path):
    path = tmp_path / "settings.db"
    s = SettingsStore(path)
    s.set_many({"late_tolerance_min": 15, "timezone": "Africa/Tunis"})
    s.save_schedule([ShiftDef("X", "Test", time(9, 0), time(18, 0))],
                    [SchedulePeriod("Dept", ("X",), frozenset({0}))], [])
    s.close()
    s = SettingsStore(path)
    assert s.get_int("late_tolerance_min") == 15
    assert [x.code for x in s.shifts()] == ["X"]
    assert s.holidays() == []
    s.close()


def test_period_round_trip(store):
    period = SchedulePeriod("Administration", ("ADM",), frozenset({0, 2}),
                            valid_from=(11, 1), valid_to=(2, 28), priority=5, name="Hiver")
    store.save_schedule(store.shifts(), [period], [Holiday(date(2026, 1, 1), "An", True)])
    assert store.periods() == [period]


@pytest.mark.parametrize("bad", [
    {"late_tolerance_min": "abc"},
    {"late_mode": "whatever"},
    {"unknown_key": "1"},
])
def test_invalid_settings_rejected(store, bad):
    with pytest.raises((ValueError, KeyError)):
        store.set_many(bad)


def test_schedule_validation(store):
    shifts = [ShiftDef("A", "A", time(8), time(16))]
    with pytest.raises(ValueError):
        store.save_schedule(shifts, [SchedulePeriod("D", ("B",), frozenset({0}))], [])
    with pytest.raises(ValueError):
        store.save_schedule(shifts + shifts, [], [])
    assert {s.code for s in store.shifts()} >= {"ADM"}  # unchanged after failures


def test_seeded_config_drives_engine(store):
    rahma = Employee("302", "Rahma", "Achour", "Administration")
    results = compute([rahma], [], store.engine_config(), date(2026, 7, 25), date(2026, 7, 26))
    assert [r.status for r in results] == [Status.HOLIDAY, Status.REST]


def test_db_params(store):
    p = store.db_params()
    assert (p.host, p.port, p.dbname, p.user, p.timezone) == (
        "192.168.10.6", 7497, "biotime", "postgres", "Africa/Tunis")


def test_weekdays_label():
    from zkreport.ui.labels_fr import weekdays_label
    assert weekdays_label(range(5)) == "Lun–Ven"
    assert weekdays_label([0, 2, 5]) == "Lun, Mer, Sam"
    assert weekdays_label([5, 6]) == "Sam, Dim"
    assert weekdays_label(range(7)) == "Tous les jours"
