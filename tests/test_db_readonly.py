"""Read-only guarantees of the DB layer. The live test is skipped when the DB is unreachable."""
import socket
from datetime import date

import pytest

from zkreport.db.connection import DbParams, connection_kwargs, read_only_options
from zkreport.db.repository import ZkRepository, open_repository, punch_bounds

PARAMS = DbParams("192.168.10.6", 7497, "biotime", "postgres", "Africa/Tunis", 3)


def test_options_force_read_only_and_timezone():
    assert read_only_options("Africa/Tunis") == (
        "-c default_transaction_read_only=on -c TimeZone=Africa/Tunis")
    kwargs = connection_kwargs(PARAMS, None)
    assert kwargs["options"] == read_only_options("Africa/Tunis")
    assert "password" not in kwargs
    assert connection_kwargs(PARAMS, "secret")["password"] == "secret"


@pytest.mark.parametrize("tz", ["Africa/Tunis; DROP", "a b", ""])
def test_options_reject_injection(tz):
    with pytest.raises(ValueError):
        read_only_options(tz)


@pytest.mark.parametrize("sql", [
    "INSERT INTO x VALUES (1)", "UPDATE x SET a = 1", "DELETE FROM x", "DROP TABLE x",
    "SELECT 1; DELETE FROM x", "  create table x(a int)",
])
def test_repository_rejects_writes(sql):
    repo = ZkRepository(conn=None)
    with pytest.raises(PermissionError):
        repo._query(sql)


def test_punch_bounds_cover_overnight_margin():
    start, end = punch_bounds(date(2026, 9, 1), date(2026, 9, 1), "Africa/Tunis")
    assert start.isoformat() == "2026-08-31T00:00:00+01:00"
    assert end.isoformat() == "2026-09-03T00:00:00+01:00"


def _reachable(host, port):
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not _reachable(PARAMS.host, PARAMS.port), reason="ZKBio DB unreachable")
def test_live_connection_is_read_only():
    # No write probe on purpose: the hard rule forbids any DDL/DML, even rejected ones.
    with open_repository(PARAMS, None) as repo:
        assert repo._conn.read_only is True
        info = repo.server_info()
        assert info["read_only"] == "on"
        assert info["timezone"] == "Africa/Tunis"
        assert repo.employees()
