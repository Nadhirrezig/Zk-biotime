"""Read-only PostgreSQL access to the ZKBio Time database.

Every connection is opened with default_transaction_read_only=on and the configured
TimeZone, flagged read_only at the driver level, and verified before use.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import psycopg

_TZ_NAME = re.compile(r"^[A-Za-z0-9_+\-/]+$")


class ReadOnlyViolation(RuntimeError):
    """The server did not confirm a read-only session."""


@dataclass(frozen=True)
class DbParams:
    host: str
    port: int
    dbname: str
    user: str
    timezone: str
    connect_timeout: int

    @property
    def keyring_account(self) -> str:
        return f"{self.user}@{self.host}:{self.port}/{self.dbname}"


def read_only_options(timezone: str) -> str:
    if not _TZ_NAME.match(timezone or ""):
        raise ValueError(f"Invalid time zone name: {timezone!r}")
    return f"-c default_transaction_read_only=on -c TimeZone={timezone}"


def connection_kwargs(params: DbParams, password: str | None) -> dict:
    kwargs = dict(
        host=params.host,
        port=params.port,
        dbname=params.dbname,
        user=params.user,
        options=read_only_options(params.timezone),
        connect_timeout=params.connect_timeout,
        application_name="zkreport-readonly",
    )
    if password:
        kwargs["password"] = password
    return kwargs


def connect(params: DbParams, password: str | None = None) -> psycopg.Connection:
    conn = psycopg.connect(**connection_kwargs(params, password))
    try:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute("SHOW default_transaction_read_only")
            (value,) = cur.fetchone()
        conn.rollback()
        if str(value).lower() != "on":
            raise ReadOnlyViolation(f"default_transaction_read_only = {value}")
    except Exception:
        conn.close()
        raise
    return conn
