"""Main window: dark sidebar + page stack (Journée, Employé), background loading, auto refresh."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable
from zoneinfo import ZoneInfo

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

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
from .sidebar import Sidebar
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

        self.error_banner = QLabel()
        self.error_banner.setWordWrap(True)
        self.error_banner.setStyleSheet(
            f"background:{theme.ABSENT.tint}; color:{theme.ABSENT.text}; padding:10px 14px;"
            f" border:1px solid #FECDCA; border-radius:10px; font-weight:600;")
        self.error_banner.hide()

        self.daily = DailyPage()
        self.employee = EmployeePage()
        self.stack = QStackedWidget()
        self.stack.addWidget(self.daily)
        self.stack.addWidget(self.employee)
        self.sidebar = Sidebar([("Journée", "calendar"), ("Employé", "user")])
        self.sidebar.page_requested.connect(self.stack.setCurrentIndex)
        self.sidebar.settings_requested.connect(self.open_settings)
        self.sidebar.refresh_requested.connect(self.refresh)
        self.status = self.sidebar.status
        QShortcut(QKeySequence("F5"), self, activated=self.refresh)

        self.daily.day_changed.connect(self.refresh_day)
        self.daily.employee_requested.connect(self.show_employee)
        self.employee.selection_changed.connect(self.refresh_employee)
        for button in (self.daily.export_button, self.employee.export_button):
            button.message.connect(self._flash)
        self._message_timer = QTimer(self)
        self._message_timer.setSingleShot(True)
        self._message_timer.timeout.connect(self.sidebar.message.hide)

        content = QWidget()
        content.setObjectName("page")
        content.setStyleSheet(f"#page {{ background: {theme.PAGE_BG}; }}")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(28, 22, 28, 22)
        content_layout.setSpacing(12)
        content_layout.addWidget(self.error_banner)
        content_layout.addWidget(self.stack, 1)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(content, 1)
        self.setCentralWidget(central)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self._apply_settings()

    # -- setup -----------------------------------------------------------------
    def _db_factory(self) -> RepoFactory:
        params = self.store.db_params()
        return db_repo_factory(params, secrets.get_password(params.keyring_account))

    def _flash(self, text: str) -> None:
        self.sidebar.message.setText(text)
        self.sidebar.message.show()
        self._message_timer.start(8000)

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
        self.stack.setCurrentWidget(self.employee)
        self.sidebar.set_current(1)
        self.employee.select_employee(emp_code)

    def _status_text(self, report: DayReport) -> str:
        interval = self.store.get_int("refresh_interval_sec")
        every = f"{interval // 60} min" if interval % 60 == 0 else f"{interval} s"
        parts = [f"Mis à jour à {report.loaded_at:%H:%M:%S}",
                 f"Actualisation : toutes les {every}"]
        if report.last_punch:
            parts.append(f"Dernier pointage : {report.last_punch:%d/%m/%Y %H:%M}")
            now = datetime.now(ZoneInfo(self.config.timezone))
            if now - report.last_punch > timedelta(hours=24):
                parts.append("<span style='color:#FEC84B'>⚠ Aucun pointage reçu depuis "
                             "plus de 24 h (pointeuse déconnectée ?)</span>")
        return "<br>".join(parts)

    def closeEvent(self, event) -> None:
        self.timer.stop()
        self._runner.wait_all()
        super().closeEvent(event)
