"""load_day_report: DB rows -> engine -> sorted report, with a fake repository."""
from datetime import date

import psycopg

from fakes import FakeRepository, fake_factory
from zkreport.engine.models import Missing, Status
from zkreport.service import friendly_error, load_day_report
from zkreport.store.settings_store import SettingsStore


def test_day_report_with_seeded_config(tmp_path):
    store = SettingsStore(tmp_path / "s.db")
    repo = FakeRepository()
    report = load_day_report(fake_factory(repo), store.engine_config(), date(2026, 9, 24))
    by_code = {r.emp_code: r for r in report.results}
    assert "1" not in by_code                                   # excluded
    assert by_code["302"].missing is Missing.ARRIVAL            # Rahma 16:52 only
    assert by_code["247"].shift_code == "PRD_M"
    assert by_code["215"].status is Status.SINGLE_PUNCH         # night, no departure
    assert by_code["215"].missing is Missing.DEPARTURE
    assert by_code["227"].status is Status.COMPLETE
    assert by_code["155"].status is Status.ABSENT
    s = report.summary
    assert (s.employees, s.present, s.single_punch, s.absent) == (5, 4, 2, 1)
    # punches requested with a one-day margin on both sides
    _, start, end = repo.calls[1]
    assert (start.date(), end.date()) == (date(2026, 9, 23), date(2026, 9, 26))
    store.close()


def test_friendly_error_is_french():
    msg = friendly_error(psycopg.OperationalError("connection refused"))
    assert msg.startswith("Connexion à la base impossible")


def test_employee_report_period(tmp_path):
    from zkreport.service import load_employee_report
    store = SettingsStore(tmp_path / "s.db")
    config = store.engine_config()
    report = load_employee_report(fake_factory(), config, "302", date(2026, 9, 1), date(2026, 9, 30))
    assert report.employee.full_name == "Rahma Achour"
    assert len(report.results) == 30
    c = report.counts
    # September: 1 single punch (24th), 1 absence (9th), Sundays are rest.
    assert (c.single, c.absent) == (1, 1)
    assert c.total == c.double + c.single
    # Swapped dates are normalised; unknown employee gives an empty report.
    swapped = load_employee_report(fake_factory(), config, "302", date(2026, 9, 30), date(2026, 9, 1))
    assert (swapped.date_from, swapped.date_to) == (date(2026, 9, 1), date(2026, 9, 30))
    empty = load_employee_report(fake_factory(), config, "999", date(2026, 9, 1), date(2026, 9, 2))
    assert empty.employee is None and empty.results == ()
    store.close()


def test_employee_report_rejects_huge_range(tmp_path):
    import pytest
    from zkreport.service import load_employee_report
    store = SettingsStore(tmp_path / "s.db")
    with pytest.raises(ValueError):
        load_employee_report(fake_factory(), store.engine_config(), "302",
                             date(2024, 1, 1), date(2026, 1, 1))
    store.close()
