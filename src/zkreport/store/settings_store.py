"""Local SQLite store for app-owned data: settings, shifts, schedules, holidays."""
from __future__ import annotations

import sqlite3
from datetime import date, time
from pathlib import Path

from zkreport.db.connection import DbParams
from zkreport.engine.models import (
    EngineConfig,
    Holiday,
    LateMode,
    Rules,
    SchedulePeriod,
    ShiftDef,
)

from .seed import DEFAULT_HOLIDAYS, DEFAULT_PERIODS, DEFAULT_SETTINGS, DEFAULT_SHIFTS

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS shifts (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS schedule_periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    shift_codes TEXT NOT NULL,
    weekdays TEXT NOT NULL,
    valid_from TEXT,
    valid_to TEXT,
    priority INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS holidays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT NOT NULL,
    name TEXT NOT NULL,
    recurring INTEGER NOT NULL DEFAULT 0
);
"""

INT_KEYS = {
    "db_port", "db_connect_timeout_sec", "refresh_interval_sec", "duplicate_window_min",
    "late_tolerance_min", "early_leave_tolerance_min", "window_before_start_min",
    "window_after_end_min", "overtime_threshold_min",
}


def _hm(value: time) -> str:
    return value.strftime("%H:%M")


def _parse_hm(text: str) -> time:
    h, m = text.split(":")
    return time(int(h), int(m))


def _md(value: tuple[int, int] | None) -> str | None:
    return None if value is None else f"{value[0]:02d}-{value[1]:02d}"


def _parse_md(text: str | None) -> tuple[int, int] | None:
    if not text:
        return None
    m, d = text.split("-")
    return int(m), int(d)


class SettingsStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path))
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript(SCHEMA)
        self._seed()

    def close(self) -> None:
        self._db.close()

    # -- seeding ---------------------------------------------------------------
    def _seed(self) -> None:
        with self._db:
            self._db.executemany(
                "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
                DEFAULT_SETTINGS.items(),
            )
            seeded = self._db.execute("SELECT value FROM meta WHERE key = 'seeded'").fetchone()
            if seeded:
                return
            self._write_shifts(DEFAULT_SHIFTS)
            self._write_periods(DEFAULT_PERIODS)
            self._write_holidays(DEFAULT_HOLIDAYS)
            self._db.execute("INSERT INTO meta(key, value) VALUES ('seeded', '1')")

    # -- key/value settings ----------------------------------------------------
    def get(self, key: str) -> str:
        row = self._db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if row is None:
            raise KeyError(key)
        return row[0]

    def get_int(self, key: str) -> int:
        return int(self.get(key))

    def all_settings(self) -> dict[str, str]:
        return dict(self._db.execute("SELECT key, value FROM settings"))

    def set_many(self, values: dict[str, object]) -> None:
        for key, value in values.items():
            if key not in DEFAULT_SETTINGS:
                raise KeyError(f"Unknown setting: {key}")
            if key in INT_KEYS:
                int(value)  # validate
            if key == "late_mode":
                LateMode(value)
        with self._db:
            self._db.executemany(
                "INSERT INTO settings(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                [(k, str(v)) for k, v in values.items()],
            )

    # -- shifts ----------------------------------------------------------------
    def shifts(self) -> list[ShiftDef]:
        rows = self._db.execute(
            "SELECT code, name, start_time, end_time FROM shifts ORDER BY code"
        )
        return [ShiftDef(c, n, _parse_hm(s), _parse_hm(e)) for c, n, s, e in rows]

    def _write_shifts(self, shifts) -> None:
        self._db.execute("DELETE FROM shifts")
        self._db.executemany(
            "INSERT INTO shifts(code, name, start_time, end_time) VALUES (?, ?, ?, ?)",
            [(s.code, s.name, _hm(s.start), _hm(s.end)) for s in shifts],
        )

    # -- schedule periods ------------------------------------------------------
    def periods(self) -> list[SchedulePeriod]:
        rows = self._db.execute(
            "SELECT department, name, shift_codes, weekdays, valid_from, valid_to, priority "
            "FROM schedule_periods ORDER BY department, priority, id"
        )
        return [
            SchedulePeriod(
                department=dept,
                shift_codes=tuple(c for c in codes.split(",") if c),
                weekdays=frozenset(int(d) for d in days.split(",") if d != ""),
                valid_from=_parse_md(vf),
                valid_to=_parse_md(vt),
                priority=prio,
                name=name,
            )
            for dept, name, codes, days, vf, vt, prio in rows
        ]

    def _write_periods(self, periods) -> None:
        self._db.execute("DELETE FROM schedule_periods")
        self._db.executemany(
            "INSERT INTO schedule_periods(department, name, shift_codes, weekdays, "
            "valid_from, valid_to, priority) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (p.department, p.name, ",".join(p.shift_codes),
                 ",".join(str(d) for d in sorted(p.weekdays)),
                 _md(p.valid_from), _md(p.valid_to), p.priority)
                for p in periods
            ],
        )

    # -- holidays --------------------------------------------------------------
    def holidays(self) -> list[Holiday]:
        rows = self._db.execute("SELECT day, name, recurring FROM holidays ORDER BY day, id")
        return [Holiday(date.fromisoformat(d), n, bool(r)) for d, n, r in rows]

    def _write_holidays(self, holidays) -> None:
        self._db.execute("DELETE FROM holidays")
        self._db.executemany(
            "INSERT INTO holidays(day, name, recurring) VALUES (?, ?, ?)",
            [(h.day.isoformat(), h.name, int(h.recurring)) for h in holidays],
        )

    # -- atomic save from the settings dialog ----------------------------------
    def save_schedule(self, shifts, periods, holidays) -> None:
        """Replace shifts, periods and holidays in one transaction after validation."""
        codes = [s.code for s in shifts]
        if len(set(codes)) != len(codes):
            raise ValueError("Codes d'équipe en double")
        if any(not c.strip() for c in codes):
            raise ValueError("Code d'équipe vide")
        for p in periods:
            unknown = [c for c in p.shift_codes if c not in codes]
            if unknown:
                raise ValueError(f"Planning « {p.name or p.department} » : équipe inconnue {unknown}")
            if not p.shift_codes:
                raise ValueError(f"Planning « {p.name or p.department} » : aucune équipe")
            if (p.valid_from is None) != (p.valid_to is None):
                raise ValueError(f"Planning « {p.name or p.department} » : période incomplète")
        with self._db:
            self._write_shifts(shifts)
            self._write_periods(periods)
            self._write_holidays(holidays)

    # -- derived objects -------------------------------------------------------
    def rules(self) -> Rules:
        return Rules(
            duplicate_window_min=self.get_int("duplicate_window_min"),
            late_tolerance_min=self.get_int("late_tolerance_min"),
            early_leave_tolerance_min=self.get_int("early_leave_tolerance_min"),
            late_mode=LateMode(self.get("late_mode")),
            window_before_start_min=self.get_int("window_before_start_min"),
            window_after_end_min=self.get_int("window_after_end_min"),
            overtime_threshold_min=self.get_int("overtime_threshold_min"),
        )

    def excluded_emp_codes(self) -> frozenset[str]:
        raw = self.get("excluded_emp_codes")
        return frozenset(c.strip() for c in raw.replace(";", ",").split(",") if c.strip())

    def engine_config(self) -> EngineConfig:
        return EngineConfig(
            timezone=self.get("timezone"),
            rules=self.rules(),
            shifts=tuple(self.shifts()),
            periods=tuple(self.periods()),
            holidays=tuple(self.holidays()),
            excluded_emp_codes=self.excluded_emp_codes(),
        )

    def db_params(self) -> DbParams:
        return DbParams(
            host=self.get("db_host"),
            port=self.get_int("db_port"),
            dbname=self.get("db_name"),
            user=self.get("db_user"),
            timezone=self.get("timezone"),
            connect_timeout=self.get_int("db_connect_timeout_sec"),
        )
