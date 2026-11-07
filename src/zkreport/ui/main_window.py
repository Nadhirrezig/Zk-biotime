"""Main window: 'Journée' and 'Employé' tabs, background loading, auto refresh."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable
from zoneinfo import ZoneInfo

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import QLabel, QMainWindow, QTabWidget, QToolBar, QVBoxLayout, QWidget

from zkreport.service import (
    DayReport,
    EmployeeReport,
    RepoFactory,
    db_repo_factory,
    load_day_report,
    load_employee_report,
)
from zkreport.store import secrets
from zkreport.store.settings_store import SettingsStore

from . import labels_fr as fr
from . import theme
from .daily_page import DailyPage
from .employee_page import EmployeePage
from .settings_dialog import SettingsDialog
from .workers import JobRunner

# Returns the repository factory to use for the next load (DB by default; fakes in tests).
RepoFactoryProvider = Callable[[], RepoFactory]


class MainWindow(QMainWindow):
    def __init__(self, store: SettingsStore,
                 repo_factory_provider: RepoFactoryProvider | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ZK Rapport de présence — lecture seule")
        self.resize(1280, 760)
        self.store = store
        self._provider = repo_factory_provider or self._db_factory
        self._jobs: dict[str, int | None] = {"day": None, "employee": None}
        self._requested: dict[str, object] = {}   # what each running job was asked for
        self._pending: set[str] = set()
        self._runner = JobRunner(self)
        self._runner.done.connect(self._on_done)
        self._runner.error.connect(self._on_failed)

        self._build_toolbar()
        self.error_banner = QLabel()
        self.error_banner.setWordWrap(True)
        self.error_banner.setStyleSheet(
            f"background:{theme.LATE.tint}; color:{theme.LATE.text}; padding:6px;"
            " border-radius:4px;")
        self.error_banner.hide()

        self.daily = DailyPage()
        self.employee = EmployeePage()
        self.tabs = QTabWidget()
        self.tabs.addTab(self.daily, "Journée")
        self.tabs.addTab(self.employee, "Employé")
        self.daily.day_changed.connect(self.refresh_day)
        self.daily.employee_requested.connect(self.show_employee)
        self.employee.selection_changed.connect(self.refresh_employee)
        for bar in (self.daily.export_bar, self.employee.export_bar):
            bar.message.connect(lambda text: self.statusBar().showMessage(text, 8000))

        central = QWidget()
        central.setObjectName("page")
        central.setStyleSheet(f"#page {{ background: {theme.PAGE_BG}; }}")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 12, 16, 8)
        layout.setSpacing(10)
        layout.addWidget(self.error_banner)
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        self.status = QLabel()
        self.statusBar().addPermanentWidget(self.status, 1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self._apply_settings()

    # -- setup -----------------------------------------------------------------
    def _db_factory(self) -> RepoFactory:
        params = self.store.db_params()
        return db_repo_factory(params, secrets.get_password(params.keyring_account))

    def _build_toolbar(self) -> None:
        bar = QToolBar("Principal")
        bar.setMovable(False)
        self.addToolBar(bar)
        refresh = QAction("Actualiser", self)
        refresh.setShortcut(QKeySequence("F5"))
        refresh.triggered.connect(self.refresh)
        settings = QAction("Paramètres…", self)
        settings.triggered.connect(self.open_settings)
        bar.addAction(refresh)
        bar.addSeparator()
        bar.addAction(settings)

    def _apply_settings(self) -> None:
        self.config = self.store.engine_config()
        self.timer.start(self.store.get_int("refresh_interval_sec") * 1000)

    def open_settings(self) -> None:
        departments = [r.department for r in self.daily.report.results] \
            if self.daily.report else []
        dialog = SettingsDialog(self.store, departments, self)
        if dialog.exec():
            self._apply_settings()
            self.refresh()

    # -- loading ---------------------------------------------------------------
    def refresh(self) -> None:
        self.refresh_day()
        self.refresh_employee()

    def refresh_day(self) -> None:
        config, day = self.config, self.daily.selected_day()
        self._start("day", day, lambda factory: load_day_report(factory, config, day),
                    f"Chargement du {day:%d/%m/%Y}…")

    def refresh_employee(self) -> None:
        selection = self.employee.selection()
        if selection is None:
            return
        code, date_from, date_to = selection
        config = self.config
        self._start("employee", selection,
                    lambda factory: load_employee_report(factory, config, code, date_from, date_to),
                    "Chargement de l'employé…")

    def _current_request(self, kind: str):
        return self.daily.selected_day() if kind == "day" else self.employee.selection()

    def _start(self, kind: str, request, work, status: str) -> None:
        if self._runner.is_running(self._jobs[kind]):
            self._pending.add(kind)   # reload once the running job ends
            return
        try:
            factory = self._provider()
        except Exception as exc:  # e.g. invalid settings
            self._show_error(str(exc))
            return
        self.status.setText(status)
        self._requested[kind] = request
        self._jobs[kind] = self._runner.start(lambda: work(factory))

    def _kind_of(self, job_id: int) -> str | None:
        return next((k for k, j in self._jobs.items() if j == job_id), None)

    def _on_done(self, job_id: int, report: object) -> None:
        kind = self._kind_of(job_id)
        if kind is None:
            return
        self._jobs[kind] = None
        self.error_banner.hide()
        reload = kind in self._pending or self._requested.get(kind) != self._current_request(kind)
        self._pending.discard(kind)
        if kind == "day":
            self.daily.set_report(report)
            self._update_employee_list(report)
            self.status.setText(self._status_text(report))
        else:
            self.employee.set_report(report)
            self.status.setText(self._status_text(self.daily.report) if self.daily.report
                                else f"Mis à jour à {report.loaded_at:%H:%M:%S}")
        if reload:  # the selection changed while loading
            if kind == "day":
                self.refresh_day()
            else:
                self.refresh_employee()

    def _on_failed(self, job_id: int, message: str) -> None:
        kind = self._kind_of(job_id)
        if kind is None:
            return
        self._jobs[kind] = None
        self._pending.discard(kind)
        self._show_error(message)

    def _show_error(self, message: str) -> None:
        self.error_banner.setText(message + "  — Vérifiez les paramètres de connexion.")
        self.error_banner.show()
        self.status.setText(f"Échec du chargement ({datetime.now():%H:%M:%S}).")

    def _update_employee_list(self, report: DayReport) -> None:
        seen: dict[str, str] = {}
        for r in report.results:
            seen.setdefault(r.emp_code, fr.employee_label(r.name, r.emp_code))
        self.employee.set_employees(sorted(seen.items(), key=lambda kv: kv[1].casefold()))

    def show_employee(self, emp_code: str) -> None:
        self.tabs.setCurrentWidget(self.employee)
        self.employee.select_employee(emp_code)

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
