"""Glue between the DB layer and the engine. No Qt: runs inside worker threads."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable, ContextManager, Iterable
from zoneinfo import ZoneInfo

import psycopg

from zkreport.db.connection import DbParams, ReadOnlyViolation
from zkreport.db.repository import ZkRepository, open_repository, punch_bounds
from zkreport.engine import Summary, compute, summarize
from zkreport.engine.models import DayResult, Employee, EngineConfig, Status

RepoFactory = Callable[[], ContextManager[ZkRepository]]

MAX_RANGE_DAYS = 400


@dataclass(frozen=True)
class DayReport:
    day: date
    results: tuple[DayResult, ...]
    summary: Summary
    last_punch: datetime | None
    loaded_at: datetime


@dataclass(frozen=True)
class DayCounts:
    """Basic counts shown to users: double / single punch, absent, total punched."""
    double: int
    single: int
    absent: int

    @property
    def total(self) -> int:
        return self.double + self.single

    @classmethod
    def from_results(cls, results: Iterable[DayResult]) -> "DayCounts":
        results = list(results)
        return cls(
            double=sum(r.status is Status.COMPLETE for r in results),
            single=sum(r.status is Status.SINGLE_PUNCH for r in results),
            absent=sum(r.status is Status.ABSENT for r in results),
        )


@dataclass(frozen=True)
class EmployeeReport:
    employee: Employee | None
    date_from: date
    date_to: date
    results: tuple[DayResult, ...]
    counts: DayCounts
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


def load_employee_report(repo_factory: RepoFactory, config: EngineConfig, emp_code: str,
                         date_from: date, date_to: date) -> EmployeeReport:
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    if (date_to - date_from).days + 1 > MAX_RANGE_DAYS:
        raise ValueError(f"Période trop longue (maximum {MAX_RANGE_DAYS} jours)")
    start, end = punch_bounds(date_from, date_to, config.timezone)
    with repo_factory() as repo:
        employee = next((e for e in repo.employees() if e.emp_code == emp_code), None)
        punches = repo.punches(start, end, emp_code) if employee else []
    # compute() returns one employee's rows in day order already.
    results = compute([employee], punches, config, date_from, date_to) if employee else []
    return EmployeeReport(
        employee=employee,
        date_from=date_from,
        date_to=date_to,
        results=tuple(results),
        counts=DayCounts.from_results(results),
        loaded_at=datetime.now(ZoneInfo(config.timezone)),
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
    if isinstance(exc, ValueError):
        return str(exc)
    return f"{exc.__class__.__name__} : {exc}"
