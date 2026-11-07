"""Seed defaults. Observed patterns only: the client must confirm them in the config page."""
from datetime import date, time

from zkreport.engine.models import Holiday, SchedulePeriod, ShiftDef

DEFAULT_SETTINGS: dict[str, str] = {
    # Connection (dev access through the VM port forward; password lives in keyring)
    "db_host": "192.168.10.6",
    "db_port": "7497",
    "db_name": "biotime",
    "db_user": "postgres",
    "db_connect_timeout_sec": "5",
    # General
    "timezone": "Africa/Tunis",
    "refresh_interval_sec": "300",
    "excluded_emp_codes": "1",
    # Rules
    "duplicate_window_min": "5",
    "window_before_start_min": "240",
    "window_after_end_min": "360",
}

ALL_DAYS = frozenset(range(7))
MON_FRI = frozenset(range(5))

DEFAULT_SHIFTS = (
    ShiftDef("ADM", "Administration", time(8, 0), time(17, 0)),
    ShiftDef("ADM_SAM", "Administration samedi", time(8, 0), time(13, 0)),
    ShiftDef("ADM_ETE", "Administration été", time(8, 0), time(14, 0)),
    ShiftDef("PRD_M", "Production matin", time(6, 0), time(14, 0)),
    ShiftDef("PRD_A", "Production après-midi", time(14, 0), time(22, 0)),
    ShiftDef("PRD_N", "Production nuit", time(22, 0), time(6, 0)),
    ShiftDef("GARD", "Gardiennage", time(18, 0), time(6, 0)),
)

DEFAULT_PERIODS = (
    SchedulePeriod("Administration", ("ADM",), MON_FRI, name="Administration lun-ven"),
    SchedulePeriod("Administration", ("ADM_SAM",), frozenset({5}), name="Administration samedi"),
    SchedulePeriod("Administration", ("ADM_ETE",), MON_FRI, valid_from=(7, 1), valid_to=(8, 31),
                   priority=10, name="Administration été (séance unique)"),
    SchedulePeriod("Production", ("PRD_M", "PRD_A", "PRD_N"), ALL_DAYS, name="Production 3x8"),
    SchedulePeriod("Gardiennage", ("GARD",), ALL_DAYS, name="Gardiennage"),
)

# Fixed-date Tunisian public holidays (recurring) + 2026 lunar holidays (estimated dates).
DEFAULT_HOLIDAYS = (
    Holiday(date(2026, 1, 1), "Jour de l'An", True),
    Holiday(date(2026, 3, 20), "Fête de l'Indépendance", True),
    Holiday(date(2026, 4, 9), "Journée des Martyrs", True),
    Holiday(date(2026, 5, 1), "Fête du Travail", True),
    Holiday(date(2026, 7, 25), "Fête de la République", True),
    Holiday(date(2026, 8, 13), "Fête de la Femme", True),
    Holiday(date(2026, 10, 15), "Fête de l'Évacuation", True),
    Holiday(date(2026, 12, 17), "Fête de la Révolution", True),
    Holiday(date(2026, 3, 21), "Aïd el-Fitr (date à confirmer)", False),
    Holiday(date(2026, 5, 27), "Aïd el-Idha (date à confirmer)", False),
    Holiday(date(2026, 5, 28), "Aïd el-Idha 2e jour (date à confirmer)", False),
    Holiday(date(2026, 6, 16), "Ras el Am el Hijri (date à confirmer)", False),
    Holiday(date(2026, 8, 25), "Mouled (date à confirmer)", False),
)
