"""Main window: date picker, dashboard counts, daily table, auto refresh."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable
from zoneinfo import ZoneInfo

from PyQt6.QtCore import QDate, QTimer
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QDateEdit,
    QLabel,
    QMainWindow,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from zkreport.engine.models import EngineConfig
from zkreport.service import DayReport, db_repo_factory, load_day_report
from zkreport.store import secrets
from zkreport.store.settings_store import SettingsStore

from .daily_view import DailyView
from .dashboard import Dashboard
from .settings_dialog import SettingsDialog
from .workers import JobRunner

# loader(config, day) -> DayReport ; injectable for tests and demos
Loader = Callable[[EngineConfig, date], DayReport]


def db_loader(store: SettingsStore) -> Loader:
    def load(config: EngineConfig, day: date) -> DayReport:
        params = store.db_params()
        password = secrets.get_password(params.keyring_account)
        return load_day_report(db_repo_factory(params, password), config, day)
    return load


class MainWindow(QMainWindow):
    def __init__(self, store: SettingsStore, loader: Loader | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ZK Rapport de présence — lecture seule")
        self.resize(1280, 760)
        self.store = store
        self._loader_factory = (lambda: loader) if loader else (lambda: db_loader(store))
        self.report: DayReport | None = None
        self._job: int | None = None
        self._pending = False
        self._runner = JobRunner(self)
        self._runner.done.connect(self._on_loaded)
        self._runner.error.connect(self._on_failed)

        self._build_toolbar()
        self.error_banner = QLabel()
        self.error_banner.setWordWrap(True)
        self.error_banner.setStyleSheet(
            "background:#FDECEC; color:#B42318; padding:6px; border-radius:4px;")
        self.error_banner.hide()
        self.dashboard = Dashboard()
        self.daily = DailyView()
        self.dashboard.filter_requested.connect(self.daily.set_filter)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self.error_banner)
        layout.addWidget(self.dashboard)
        layout.addWidget(self.daily, 1)
        self.setCentralWidget(central)

        self.status = QLabel()
        self.statusBar().addWidget(self.status, 1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self._apply_settings()

    # -- UI -------------------------------------------------------------------
    def _build_toolbar(self) -> None:
        bar = QToolBar("Principal")
        bar.setMovable(False)
        self.addToolBar(bar)
        bar.addWidget(QLabel(" Date : "))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dddd dd/MM/yyyy")
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.dateChanged.connect(lambda _: self.refresh())
        bar.addWidget(self.date_edit)
        prev_day = QAction("◀ Veille", self)
        prev_day.triggered.connect(lambda: self._shift_day(-1))
        next_day = QAction("Lendemain ▶", self)
        next_day.triggered.connect(lambda: self._shift_day(1))
        today = QAction("Aujourd'hui", self)
        today.triggered.connect(lambda: self.date_edit.setDate(QDate.currentDate()))
        self.refresh_action = QAction("Actualiser", self)
        self.refresh_action.setShortcut(QKeySequence("F5"))
        self.refresh_action.triggered.connect(self.refresh)
        settings = QAction("Paramètres…", self)
        settings.triggered.connect(self.open_settings)
        for action in (prev_day, next_day, today):
            bar.addAction(action)
        bar.addSeparator()
        bar.addAction(self.refresh_action)
        bar.addSeparator()
        bar.addAction(settings)

    def _shift_day(self, delta: int) -> None:
        self.date_edit.setDate(self.date_edit.date().addDays(delta))

    def selected_day(self) -> date:
        return self.date_edit.date().toPyDate()

    def _apply_settings(self) -> None:
        self.config = self.store.engine_config()
        self.loader = self._loader_factory()
        self.timer.start(self.store.get_int("refresh_interval_sec") * 1000)

    def open_settings(self) -> None:
        departments = [r.department for r in self.report.results] if self.report else []
        dialog = SettingsDialog(self.store, departments, self)
        if dialog.exec():
            self._apply_settings()
            self.refresh()

    # -- loading ---------------------------------------------------------------
    def refresh(self) -> None:
        """Start a background load for the selected date (skipped if one is running)."""
        if self._runner.is_running(self._job):
            self._pending = True
            return
        self._pending = False
        config, day, loader = self.config, self.selected_day(), self.loader
        self.status.setText(f"Chargement du {day:%d/%m/%Y}…")
        self._job = self._runner.start(lambda: loader(config, day))

    def _on_loaded(self, job_id: int, report: object) -> None:
        if job_id != self._job:
            return
        self._job = None
        if report.day != self.selected_day():
            self.refresh()  # date changed while loading
            return
        self.report = report
        self.error_banner.hide()
        self.dashboard.set_summary(report.summary)
        self.daily.set_results(report.results)
        self.status.setText(self._status_text(report))
        if self._pending:
            self.refresh()

    def _on_failed(self, job_id: int, message: str) -> None:
        if job_id != self._job:
            return
        self._job = None
        self.error_banner.setText(message + "  — Vérifiez les paramètres de connexion.")
        self.error_banner.show()
        self.status.setText(f"Échec du chargement ({datetime.now():%H:%M:%S}).")

    def _status_text(self, report: DayReport) -> str:
        interval = self.store.get_int("refresh_interval_sec")
        every = f"{interval // 60} min" if interval % 60 == 0 else f"{interval} s"
        parts = [f"Mis à jour à {report.loaded_at:%H:%M:%S}",
                 f"Actualisation automatique : toutes les {every}"]
        if report.last_punch:
            parts.append(f"Dernier pointage reçu : {report.last_punch:%d/%m/%Y %H:%M}")
            now = datetime.now(ZoneInfo(self.config.timezone))
            if now - report.last_punch > timedelta(hours=24):
                parts.append("⚠ aucun pointage reçu depuis plus de 24 h (pointeuse déconnectée ?)")
        return "   ·   ".join(parts)

    def closeEvent(self, event) -> None:
        self.timer.stop()
        self._runner.wait_all()
        super().closeEvent(event)
