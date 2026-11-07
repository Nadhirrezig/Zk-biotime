"""Glue between the DB layer and the engine. No Qt: runs inside worker threads."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable, ContextManager
from zoneinfo import ZoneInfo

import psycopg

from zkreport.db.connection import DbParams, ReadOnlyViolation
from zkreport.db.repository import ZkRepository, open_repository, punch_bounds
from zkreport.engine import Summary, compute, summarize
from zkreport.engine.models import DayResult, EngineConfig

RepoFactory = Callable[[], ContextManager[ZkRepository]]


@dataclass(frozen=True)
class DayReport:
    day: date
    results: tuple[DayResult, ...]
    summary: Summary
    last_punch: datetime | None
    loaded_at: datetime


def db_repo_factory(params: DbParams, password: str | None) -> RepoFactory:
    return lambda: open_repository(params, password)


def load_day_report(repo_factory: RepoFactory, config: EngineConfig, day: date) -> DayReport:
    tz = ZoneInfo(config.timezone)
    start, end = punch_bounds(day, day, config.timezone)
    with repo_factory() as repo:
        employees = repo.employees()
        punches = repo.punches(start, end)
        last = repo.last_punch_time()
    results = compute(employees, punches, config, day, day)
    results.sort(key=lambda r: (r.department.casefold(), r.name.casefold(), r.emp_code))
    return DayReport(
        day=day,
        results=tuple(results),
        summary=summarize(results),
        last_punch=last.astimezone(tz) if last else None,
        loaded_at=datetime.now(tz),
    )


def check_connection(repo_factory: RepoFactory) -> dict:
    with repo_factory() as repo:
        return repo.server_info()


def friendly_error(exc: BaseException) -> str:
    """French message for the UI."""
    if isinstance(exc, ReadOnlyViolation):
        return f"La session n'est pas en lecture seule ({exc}). Connexion refusée."
    if isinstance(exc, psycopg.OperationalError):
        text = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
        return f"Connexion à la base impossible : {text}"
    if isinstance(exc, psycopg.Error):
        return f"Erreur de la base de données : {exc}"
    return f"{exc.__class__.__name__} : {exc}"
