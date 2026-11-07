"""SELECT-only queries against ZKBio Time tables."""
from __future__ import annotations

import re
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from zkreport.engine.models import Employee, Punch

from .connection import DbParams, connect

_ALLOWED = re.compile(r"^\s*(SELECT|WITH|SHOW)\b", re.IGNORECASE)

SQL_EMPLOYEES = """
SELECT e.emp_code,
       COALESCE(e.first_name, ''),
       COALESCE(e.last_name, ''),
       COALESCE(d.dept_name, ''),
       (SELECT MIN(r.resign_date) FROM personnel_resign r WHERE r.employee_id = e.id)
FROM personnel_employee e
LEFT JOIN personnel_department d ON d.id = e.department_id
ORDER BY e.emp_code_digit NULLS LAST, e.emp_code
"""

SQL_PUNCHES = """
SELECT t.emp_code, t.punch_time
FROM iclock_transaction t
WHERE t.punch_time >= %s AND t.punch_time < %s
ORDER BY t.emp_code, t.punch_time
"""

SQL_PUNCHES_ONE = """
SELECT t.emp_code, t.punch_time
FROM iclock_transaction t
WHERE t.punch_time >= %s AND t.punch_time < %s AND t.emp_code = %s
ORDER BY t.punch_time
"""

SQL_LAST_PUNCH = "SELECT MAX(punch_time) FROM iclock_transaction"

SQL_SERVER_INFO = """
SELECT current_setting('server_version'),
       current_setting('TimeZone'),
       current_setting('default_transaction_read_only'),
       (SELECT COUNT(*) FROM personnel_employee),
       (SELECT COUNT(*) FROM iclock_transaction)
"""


class ZkRepository:
    def __init__(self, conn):
        self._conn = conn

    def _query(self, sql: str, params: tuple = ()) -> list[tuple]:
        if not _ALLOWED.match(sql) or ";" in sql.strip().rstrip(";"):
            raise PermissionError("Only single SELECT/WITH/SHOW statements are allowed")
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        self._conn.rollback()  # end the read-only transaction, keep nothing open
        return rows

    def server_info(self) -> dict:
        version, tz, ro, employees, punches = self._query(SQL_SERVER_INFO)[0]
        return {"version": version, "timezone": tz, "read_only": ro,
                "employees": employees, "punches": punches}

    def employees(self) -> list[Employee]:
        return [
            Employee(str(code), first or "", last or "", dept or "", resign)
            for code, first, last, dept, resign in self._query(SQL_EMPLOYEES)
        ]

    def punches(self, start: datetime, end: datetime, emp_code: str | None = None) -> list[Punch]:
        if emp_code is None:
            rows = self._query(SQL_PUNCHES, (start, end))
        else:
            rows = self._query(SQL_PUNCHES_ONE, (start, end, emp_code))
        return [Punch(str(code), ts) for code, ts in rows]

    def last_punch_time(self) -> datetime | None:
        return self._query(SQL_LAST_PUNCH)[0][0]


@contextmanager
def open_repository(params: DbParams, password: str | None):
    conn = connect(params, password)
    try:
        yield ZkRepository(conn)
    finally:
        conn.close()


def punch_bounds(date_from: date, date_to: date, timezone: str) -> tuple[datetime, datetime]:
    """[date_from - 1 day, date_to + 2 days) in local time: covers overnight shifts."""
    tz = ZoneInfo(timezone)
    start = datetime.combine(date_from - timedelta(days=1), time(0), tzinfo=tz)
    end = datetime.combine(date_to + timedelta(days=2), time(0), tzinfo=tz)
    return start, end
