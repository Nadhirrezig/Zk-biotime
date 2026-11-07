"""Shared fixtures: engine configs mirroring the seeded defaults, Rahma punches."""
import csv
from datetime import datetime, time
from pathlib import Path

import pytest

from zkreport.engine.models import (
    EngineConfig,
    Employee,
    Holiday,
    LateMode,
    Punch,
    Rules,
    SchedulePeriod,
    ShiftDef,
)

FIXTURES = Path(__file__).parent / "fixtures"
TZ = "Africa/Tunis"
ALL_DAYS = frozenset(range(7))
MON_FRI = frozenset(range(5))


def make_rules(**overrides) -> Rules:
    values = dict(
        duplicate_window_min=5,
        late_tolerance_min=10,
        early_leave_tolerance_min=10,
        late_mode=LateMode.AFTER_TOLERANCE,
        window_before_start_min=240,
        window_after_end_min=360,
        overtime_threshold_min=30,
    )
    values.update(overrides)
    return Rules(**values)


def admin_config(start: str = "08:00", rules: Rules | None = None, holidays=()) -> EngineConfig:
    h, m = (int(x) for x in start.split(":"))
    shifts = (
        ShiftDef("ADM_REG", "Administration", time(h, m), time(17, 0)),
        ShiftDef("ADM_SAT", "Administration samedi", time(h, m), time(13, 0)),
        ShiftDef("ADM_SUM", "Administration été", time(h, m), time(14, 0)),
    )
    periods = (
        SchedulePeriod("Administration", ("ADM_REG",), MON_FRI, name="Normal"),
        SchedulePeriod("Administration", ("ADM_SAT",), frozenset({5}), name="Samedi"),
        SchedulePeriod(
            "Administration", ("ADM_SUM",), MON_FRI,
            valid_from=(7, 1), valid_to=(8, 31), priority=10, name="Été",
        ),
    )
    return EngineConfig(
        timezone=TZ,
        rules=rules or make_rules(),
        shifts=shifts,
        periods=periods,
        holidays=tuple(holidays),
    )


def production_config(rules: Rules | None = None) -> EngineConfig:
    shifts = (
        ShiftDef("PRD_M", "Matin", time(6, 0), time(14, 0)),
        ShiftDef("PRD_A", "Après-midi", time(14, 0), time(22, 0)),
        ShiftDef("PRD_N", "Nuit", time(22, 0), time(6, 0)),
    )
    periods = (
        SchedulePeriod("Production", ("PRD_M", "PRD_A", "PRD_N"), ALL_DAYS, name="3x8"),
    )
    return EngineConfig(timezone=TZ, rules=rules or make_rules(), shifts=shifts, periods=periods)


TUNISIA_HOLIDAYS = (
    Holiday(datetime(2026, 7, 25).date(), "Fête de la République", recurring=True),
    Holiday(datetime(2026, 10, 15).date(), "Fête de l'Évacuation", recurring=True),
)


@pytest.fixture
def rahma() -> Employee:
    return Employee("302", "Rahma", "Achour", "Administration")


@pytest.fixture
def rahma_punches() -> list[Punch]:
    with (FIXTURES / "rahma_punches.csv").open(encoding="utf-8") as fh:
        return [
            Punch(row["emp_code"], datetime.fromisoformat(row["punch_time"]))
            for row in csv.DictReader(fh)
        ]
