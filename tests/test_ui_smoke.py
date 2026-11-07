"""Offscreen smoke tests of the PyQt6 UI with a fake data source."""
import os
import time
from contextlib import contextmanager
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import QApplication

from fakes import fake_factory
from zkreport.engine.models import Status
from zkreport.store.settings_store import SettingsStore
from zkreport.ui import labels_fr as fr
from zkreport.ui.main_window import MainWindow
from zkreport.ui.settings_dialog import SettingsDialog
from zkreport.ui.table_export import write_pdf


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def store(tmp_path):
    s = SettingsStore(tmp_path / "settings.db")
    yield s
    s.close()


@pytest.fixture
def window(app, store):
    w = MainWindow(store, repo_factory_provider=lambda: fake_factory())
    yield w
    w.close()


def wait_for(app, predicate, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("timeout")


def idle(window):
    return all(j is None for j in window._jobs.values())


def show_day(app, window, day):
    window.daily.date_edit.setDate(QDate(day.year, day.month, day.day))
    window.refresh_day()
    wait_for(app, lambda: window.daily.report is not None and window.daily.report.day == day
             and idle(window))


def test_daily_cards_and_filters(app, window):
    show_day(app, window, date(2026, 9, 24))
    cards = window.daily.cards
    assert cards.value(fr.FILTER_TWICE) == "2"
    assert cards.value(fr.FILTER_ONCE) == "2"
    assert cards.value(fr.FILTER_ABSENT) == "1"
    assert cards.value(fr.FILTER_PRESENT) == "4"
    table = window.daily.table
    assert table.model.columnCount() == 7

    cards.cards[fr.FILTER_ONCE].activated.emit(fr.FILTER_ONCE)      # click card
    assert {r.emp_code for r in table.visible_rows()} == {"302", "215"}
    assert cards.cards[fr.FILTER_ONCE].is_selected()
    cards.cards[fr.FILTER_ONCE].activated.emit(fr.FILTER_ONCE)      # click again clears
    assert table.filter_combo.currentData() == fr.FILTER_ALL

    table.set_filter(fr.FILTER_TWICE)
    assert {r.emp_code for r in table.visible_rows()} == {"247", "227"}
    assert cards.cards[fr.FILTER_TWICE].is_selected()
    table.set_filter(fr.FILTER_ABSENT)
    assert [r.emp_code for r in table.visible_rows()] == ["155"]
    table.set_filter(fr.FILTER_PRESENT)
    assert len(table.visible_rows()) == 4
    table.set_filter(fr.FILTER_ALL)
    table.search.setText("rahma")
    assert [r.emp_code for r in table.visible_rows()] == ["302"]


def test_employee_view_period_stats(app, window):
    show_day(app, window, date(2026, 9, 24))
    page = window.employee
    assert page.employee_combo.count() == 5          # filled from the day's list
    page.from_edit.setDate(QDate(2026, 9, 1))
    page.to_edit.setDate(QDate(2026, 9, 30))
    window.show_employee("302")                      # e.g. double-click in the daily list
    assert window.tabs.currentWidget() is page
    wait_for(app, lambda: page.report is not None and idle(window))
    report = page.report
    assert report.employee.emp_code == "302"
    assert (report.date_from, report.date_to) == (date(2026, 9, 1), date(2026, 9, 30))
    c = report.counts
    assert (c.single, c.total) == (1, c.double + 1)
    assert page.cards.value(fr.FILTER_ONCE) == "1"
    assert page.table.model.rowCount() == 30
    assert window.status.text().startswith("Mis à jour")
    page.table.set_filter(fr.FILTER_ONCE)
    (row,) = page.table.visible_rows()
    assert row.day == date(2026, 9, 24) and row.status is Status.SINGLE_PUNCH


def test_exports_from_both_pages(app, window, tmp_path):
    from openpyxl import load_workbook
    from zkreport.export import export_xlsx

    show_day(app, window, date(2026, 9, 24))
    window.daily.table.set_filter(fr.FILTER_ONCE)
    table, base = window.daily._export_data()
    assert base == "presence_2026-09-24"
    assert table.title.startswith("Présence du jeudi 24 septembre 2026")
    assert "Filtre : Pointage unique" in table.meta
    assert len(table.rows) == 2 and table.headers[0] == "Matricule"

    xlsx = tmp_path / "jour.xlsx"
    export_xlsx(table, xlsx)
    ws = load_workbook(xlsx).active
    assert ws["A1"].value == table.title
    pdf = tmp_path / "jour.pdf"
    write_pdf(table, pdf)
    assert pdf.read_bytes()[:4] == b"%PDF"

    window.employee.from_edit.setDate(QDate(2026, 9, 1))
    window.employee.to_edit.setDate(QDate(2026, 9, 30))
    window.show_employee("302")
    wait_for(app, lambda: window.employee.report is not None and idle(window))
    table, base = window.employee._export_data()
    assert base == "employe_302_2026-09-01_2026-09-30"
    assert table.title == "Rahma Achour (matricule 302)"
    assert any(line.startswith("Période : du 01/09/2026") for line in table.meta)
    write_pdf(table, tmp_path / "emp.pdf")


def test_auto_refresh_timer_uses_settings(app, store):
    store.set_many({"refresh_interval_sec": 120})
    w = MainWindow(store, repo_factory_provider=lambda: fake_factory())
    assert w.timer.isActive() and w.timer.interval() == 120_000
    w.close()


def test_load_error_shows_banner(app, store):
    @contextmanager
    def broken():
        raise RuntimeError("boom")
        yield

    w = MainWindow(store, repo_factory_provider=lambda: broken)
    w.show()
    w.refresh_day()
    wait_for(app, lambda: idle(w) and w.error_banner.isVisible())
    assert "boom" in w.error_banner.text()
    w.close()


def test_settings_dialog_save_and_connection_error(app, store, monkeypatch):
    monkeypatch.setattr("zkreport.store.secrets.set_password", lambda *a: None)
    dialog = SettingsDialog(store, ["Production"])
    assert dialog.tabs.count() == 5
    values, shifts, holidays = dialog.collect()
    assert "late_tolerance_min" not in values
    assert len(shifts) == len(store.shifts())
    assert len(holidays) == len(store.holidays())

    dialog.db_host.setText("127.0.0.1")
    dialog.db_port.setValue(1)
    dialog._test_connection()
    wait_for(app, lambda: dialog.test_button.isEnabled())
    assert "Connexion à la base impossible" in dialog.test_result.text()

    dialog.dup_window.setValue(7)
    dialog._save()
    assert store.get_int("duplicate_window_min") == 7
    assert store.get("db_host") == "127.0.0.1"
