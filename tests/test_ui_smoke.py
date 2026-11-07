"""Offscreen smoke test of the PyQt6 UI with a fake data source."""
import os
import time
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import QApplication

from fakes import fake_factory
from zkreport.engine.models import Status
from zkreport.service import load_day_report
from zkreport.store.settings_store import SettingsStore
from zkreport.ui import labels_fr as fr
from zkreport.ui.main_window import MainWindow
from zkreport.ui.settings_dialog import SettingsDialog


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def store(tmp_path):
    s = SettingsStore(tmp_path / "settings.db")
    yield s
    s.close()


def wait_for(app, predicate, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("timeout")


def fake_loader(config, day):
    return load_day_report(fake_factory(), config, day)


def show_day(app, window, day):
    window.date_edit.setDate(QDate(day.year, day.month, day.day))
    window.refresh()
    wait_for(app, lambda: window.report is not None and window.report.day == day
             and window._job is None)


def test_main_window_loads_and_filters(app, store):
    window = MainWindow(store, loader=fake_loader)
    show_day(app, window, date(2026, 9, 24))
    assert window.dashboard.value("employees") == "5"
    assert window.dashboard.value("single_punch") == "2"
    assert window.dashboard.value("absent") == "1"
    assert window.daily.model.rowCount() == 5

    window.dashboard.filter_requested.emit(fr.FILTER_ONCE)
    rows = window.daily.visible_rows()
    assert {r.emp_code for r in rows} == {"302", "215"}
    assert all(r.status is Status.SINGLE_PUNCH for r in rows)

    window.daily.set_filter(fr.FILTER_TWICE)
    assert {r.emp_code for r in window.daily.visible_rows()} == {"247", "227"}
    window.daily.set_filter(fr.FILTER_ABSENT)
    assert [r.emp_code for r in window.daily.visible_rows()] == ["155"]
    window.daily.set_filter(fr.FILTER_LATE)
    assert all(r.is_late for r in window.daily.visible_rows())
    window.daily.set_filter(fr.FILTER_ALL)
    window.daily.search.setText("rahma")
    assert [r.emp_code for r in window.daily.visible_rows()] == ["302"]
    window.daily.search.clear()

    show_day(app, window, date(2026, 7, 25))  # public holiday (seeded)
    assert window.dashboard.value("holiday") == "5"  # nobody punched on the holiday
    window.close()


def test_auto_refresh_timer_uses_settings(app, store):
    store.set_many({"refresh_interval_sec": 120})
    window = MainWindow(store, loader=fake_loader)
    assert window.timer.isActive()
    assert window.timer.interval() == 120_000
    window.close()


def test_load_error_shows_banner(app, store):
    def failing(config, day):
        raise RuntimeError("boom")

    window = MainWindow(store, loader=failing)
    window.show()
    window.refresh()
    wait_for(app, lambda: window._job is None and window.error_banner.isVisible())
    assert "boom" in window.error_banner.text()
    window.close()


def test_settings_dialog_save_and_connection_error(app, store, monkeypatch):
    monkeypatch.setattr("zkreport.store.secrets.set_password", lambda *a: None)
    dialog = SettingsDialog(store, ["Production"])
    assert dialog.tabs.count() == 5
    values, shifts, holidays = dialog.collect()
    assert values["timezone"] == "Africa/Tunis"
    assert len(shifts) == len(store.shifts())
    assert len(holidays) == len(store.holidays())

    # Connection test against a closed local port: error reported, UI not blocked.
    dialog.db_host.setText("127.0.0.1")
    dialog.db_port.setValue(1)
    dialog._test_connection()
    wait_for(app, lambda: dialog.test_button.isEnabled())
    assert "Connexion à la base impossible" in dialog.test_result.text()

    dialog.late_tol.setValue(15)
    dialog._save()
    assert store.get_int("late_tolerance_min") == 15
    assert store.get("db_host") == "127.0.0.1"


def test_dashboard_cards_filter_and_selection(app, store):
    window = MainWindow(store, loader=fake_loader)
    show_day(app, window, date(2026, 9, 24))
    dash = window.dashboard
    once_card = dash.cards[fr.FILTER_ONCE]
    late_card = dash.cards[fr.FILTER_LATE]

    # Anomaly cards: coloured count when > 0, "Aucun" when 0.
    assert once_card.value.text() == "2" and once_card.caption.text() == "50 % des présents"
    assert late_card.value.text() == "0" and late_card.caption.text() == "Aucun"
    assert dash.hero.present.text() == "4"
    assert dash.hero.expected.text() == "/ 5 attendus"
    assert dash.hero.rate.text() == "80 %"
    assert "septembre" in dash.hero.day_label.text()

    once_card.activated.emit(fr.FILTER_ONCE)          # click
    assert window.daily.filter_combo.currentData() == fr.FILTER_ONCE
    assert once_card.is_selected() and not dash.hero.is_selected()
    once_card.activated.emit(fr.FILTER_ONCE)          # click again clears
    assert window.daily.filter_combo.currentData() == fr.FILTER_ALL
    assert not once_card.is_selected()

    window.daily.set_filter(fr.FILTER_TWICE)          # combo -> chip selected
    assert dash.hero.chips[fr.FILTER_TWICE].is_selected()
    window.daily.set_filter(fr.FILTER_PRESENT)
    assert dash.hero.is_selected()

    show_day(app, window, date(2026, 7, 25))          # holiday: nobody expected
    assert dash.hero.rate.text() == "—"
    assert "Fête de la République" in dash.hero.day_label.text()
    window.close()
