"""Settings dialog: connection, general, rules, shifts/schedules, public holidays."""
from __future__ import annotations

import re
from datetime import date, datetime, time
from zoneinfo import available_timezones

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from zkreport.db.connection import DbParams
from zkreport.engine.models import Holiday, SchedulePeriod, ShiftDef
from zkreport.service import check_connection, db_repo_factory
from zkreport.store import secrets
from zkreport.store.settings_store import SettingsStore

from . import labels_fr as fr
from .theme import set_role
from .workers import JobRunner

HM = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
DM = re.compile(r"^(\d{1,2})/(\d{1,2})$")


def _spin(minimum: int, maximum: int, suffix: str, value: int, tip: str = "") -> QSpinBox:
    box = QSpinBox()
    box.setRange(minimum, maximum)
    box.setSuffix(suffix)
    box.setValue(value)
    box.setToolTip(tip)
    return box


def _parse_hm(text: str) -> time:
    m = HM.match(text.strip())
    if not m:
        raise ValueError(f"Heure invalide « {text} » (format HH:MM)")
    return time(int(m.group(1)), int(m.group(2)))


def _parse_dm(text: str) -> tuple[int, int]:
    m = DM.match(text.strip())
    if not m:
        raise ValueError(f"Date invalide « {text} » (format JJ/MM)")
    day, month = int(m.group(1)), int(m.group(2))
    date(2024, month, day)  # validates (leap year accepts 29/02)
    return month, day


def _table(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    return table


class PeriodDialog(QDialog):
    """Add/edit one department schedule period."""

    def __init__(self, shift_codes: list[tuple[str, str]], departments: list[str],
                 period: SchedulePeriod | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Planning de département")
        self.result_period: SchedulePeriod | None = None

        self.department = QComboBox()
        self.department.setEditable(True)
        self.department.addItems(departments)
        self.name = QLineEdit()

        days_box = QWidget()
        days_layout = QHBoxLayout(days_box)
        days_layout.setContentsMargins(0, 0, 0, 0)
        self.day_checks = []
        for label in fr.WEEKDAYS:
            check = QCheckBox(label)
            days_layout.addWidget(check)
            self.day_checks.append(check)

        self.shifts = QListWidget()
        for code, name in shift_codes:
            item = QListWidgetItem(f"{code} – {name}")
            item.setData(Qt.ItemDataRole.UserRole, code)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.shifts.addItem(item)

        self.seasonal = QCheckBox("Seulement entre deux dates (chaque année)")
        self.valid_from = QLineEdit()
        self.valid_from.setPlaceholderText("JJ/MM")
        self.valid_to = QLineEdit()
        self.valid_to.setPlaceholderText("JJ/MM")
        self.seasonal.toggled.connect(self.valid_from.setEnabled)
        self.seasonal.toggled.connect(self.valid_to.setEnabled)
        season = QHBoxLayout()
        season.addWidget(QLabel("du"))
        season.addWidget(self.valid_from)
        season.addWidget(QLabel("au"))
        season.addWidget(self.valid_to)
        self.priority = _spin(0, 100, "", 0, "En cas de chevauchement, la priorité la plus haute "
                                              "l'emporte (ex. horaire d'été = 10).")

        form = QFormLayout()
        form.addRow("Département", self.department)
        form.addRow("Libellé", self.name)
        form.addRow("Jours travaillés", days_box)
        form.addRow("Équipe(s)", self.shifts)
        form.addRow(self.seasonal)
        form.addRow("Période", season)
        form.addRow("Priorité", self.priority)
        help_text = QLabel(
            "Plusieurs équipes cochées = rotation : l'équipe est choisie automatiquement "
            "d'après les pointages. Les jours non cochés sont des jours de repos.")
        help_text.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(help_text)
        layout.addWidget(buttons)

        if period:
            self.department.setCurrentText(period.department)
            self.name.setText(period.name)
            for d, check in enumerate(self.day_checks):
                check.setChecked(d in period.weekdays)
            for i in range(self.shifts.count()):
                item = self.shifts.item(i)
                if item.data(Qt.ItemDataRole.UserRole) in period.shift_codes:
                    item.setCheckState(Qt.CheckState.Checked)
            if period.valid_from and period.valid_to:
                self.seasonal.setChecked(True)
                self.valid_from.setText(f"{period.valid_from[1]:02d}/{period.valid_from[0]:02d}")
                self.valid_to.setText(f"{period.valid_to[1]:02d}/{period.valid_to[0]:02d}")
            self.priority.setValue(period.priority)
        self.valid_from.setEnabled(self.seasonal.isChecked())
        self.valid_to.setEnabled(self.seasonal.isChecked())

    def _accept(self) -> None:
        try:
            department = self.department.currentText().strip()
            if not department:
                raise ValueError("Département obligatoire")
            weekdays = frozenset(d for d, c in enumerate(self.day_checks) if c.isChecked())
            if not weekdays:
                raise ValueError("Cochez au moins un jour travaillé")
            codes = tuple(self.shifts.item(i).data(Qt.ItemDataRole.UserRole)
                          for i in range(self.shifts.count())
                          if self.shifts.item(i).checkState() == Qt.CheckState.Checked)
            if not codes:
                raise ValueError("Cochez au moins une équipe")
            valid_from = valid_to = None
            if self.seasonal.isChecked():
                valid_from = _parse_dm(self.valid_from.text())
                valid_to = _parse_dm(self.valid_to.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Planning", str(exc))
            return
        self.result_period = SchedulePeriod(
            department=department, shift_codes=codes, weekdays=weekdays,
            valid_from=valid_from, valid_to=valid_to,
            priority=self.priority.value(), name=self.name.text().strip(),
        )
        self.accept()


class SettingsDialog(QDialog):
    def __init__(self, store: SettingsStore, departments: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Paramètres")
        self.resize(900, 640)
        self.store = store
        self._departments = sorted(
            set(departments or []) | {p.department for p in store.periods()}, key=str.casefold)
        self._periods: list[SchedulePeriod] = list(store.periods())
        self._runner = JobRunner(self)
        self._runner.done.connect(self._on_test_done)
        self._runner.error.connect(self._on_test_error)
        self._test_job: int | None = None

        values = store.all_settings()
        tabs = QTabWidget()
        tabs.addTab(self._connection_tab(values), "Connexion")
        tabs.addTab(self._general_tab(values), "Général")
        tabs.addTab(self._rules_tab(values), "Règles")
        tabs.addTab(self._schedule_tab(), "Horaires")
        tabs.addTab(self._holidays_tab(), "Jours fériés")
        self.tabs = tabs

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Enregistrer")
        set_role(buttons.button(QDialogButtonBox.StandardButton.Save), "primary")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

    # -- tabs --------------------------------------------------------------------
    def _connection_tab(self, v: dict) -> QWidget:
        self.db_host = QLineEdit(v["db_host"])
        self.db_port = _spin(1, 65535, "", int(v["db_port"]))
        self.db_name = QLineEdit(v["db_name"])
        self.db_user = QLineEdit(v["db_user"])
        self.db_password = QLineEdit(secrets.get_password(self._params_from_form(v).keyring_account)
                                     or "")
        self.db_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.db_password.setPlaceholderText("(aucun)")
        self.db_timeout = _spin(1, 120, " s", int(v["db_connect_timeout_sec"]))
        self.test_button = QPushButton("Tester la connexion")
        self.test_button.clicked.connect(self._test_connection)
        self.test_result = QLabel()
        self.test_result.setWordWrap(True)
        self.test_result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        form = QFormLayout()
        form.addRow("Hôte", self.db_host)
        form.addRow("Port", self.db_port)
        form.addRow("Base de données", self.db_name)
        form.addRow("Utilisateur", self.db_user)
        form.addRow("Mot de passe", self.db_password)
        form.addRow("Délai de connexion", self.db_timeout)
        note = QLabel("Connexion toujours en lecture seule (default_transaction_read_only=on). "
                      "Le mot de passe est stocké dans le coffre Windows, pas dans l'application.")
        note.setWordWrap(True)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(self.test_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.test_result)
        layout.addStretch(1)
        return page

    def _general_tab(self, v: dict) -> QWidget:
        self.timezone = QComboBox()
        self.timezone.setEditable(True)
        self.timezone.addItems(sorted(available_timezones()))
        self.timezone.setCurrentText(v["timezone"])
        self.refresh = _spin(30, 86400, " s", int(v["refresh_interval_sec"]),
                             "Intervalle d'actualisation automatique")
        self.excluded = QLineEdit(v["excluded_emp_codes"])
        self.excluded.setToolTip("Matricules à ignorer, séparés par des virgules (ex. 1)")
        form = QFormLayout()
        form.addRow("Fuseau horaire", self.timezone)
        form.addRow("Actualisation automatique", self.refresh)
        form.addRow("Matricules exclus", self.excluded)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _rules_tab(self, v: dict) -> QWidget:
        self.dup_window = _spin(0, 60, " min", int(v["duplicate_window_min"]),
                                "Pointages répétés dans cet intervalle = un seul pointage")
        self.before = _spin(0, 720, " min", int(v["window_before_start_min"]),
                            "Un pointage est rattaché à l'équipe s'il a lieu au plus tôt "
                            "ce délai avant le début")
        self.after = _spin(0, 720, " min", int(v["window_after_end_min"]),
                           "… et au plus tard ce délai après la fin")
        form = QFormLayout()
        form.addRow("Fenêtre des doublons", self.dup_window)
        form.addRow("Fenêtre avant le début d'équipe", self.before)
        form.addRow("Fenêtre après la fin d'équipe", self.after)
        note = QLabel("Ces réglages servent à rattacher chaque pointage à la bonne journée "
                      "et à reconnaître les doubles badges (pointage répété).")
        note.setWordWrap(True)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    def _schedule_tab(self) -> QWidget:
        self.shift_table = _table(["Code", "Libellé", "Début (HH:MM)", "Fin (HH:MM)"])
        for s in self.store.shifts():
            self._add_shift_row(s.code, s.name, s.start.strftime("%H:%M"), s.end.strftime("%H:%M"))
        add_shift = QPushButton("Ajouter")
        add_shift.clicked.connect(lambda: self._add_shift_row("", "", "08:00", "17:00"))
        del_shift = QPushButton("Supprimer")
        del_shift.clicked.connect(lambda: self._delete_selected(self.shift_table))
        shift_box = QGroupBox("Équipes (fin ≤ début = l'équipe se termine le lendemain)")
        shift_layout = QGridLayout(shift_box)
        shift_layout.addWidget(self.shift_table, 0, 0, 1, 3)
        shift_layout.addWidget(add_shift, 1, 0)
        shift_layout.addWidget(del_shift, 1, 1)

        self.period_table = _table(["Département", "Libellé", "Jours", "Équipes",
                                    "Période", "Priorité"])
        self.period_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.period_table.doubleClicked.connect(lambda _: self._edit_period())
        self._refresh_periods()
        add_period = QPushButton("Ajouter")
        add_period.clicked.connect(lambda: self._edit_period(new=True))
        edit_period = QPushButton("Modifier")
        edit_period.clicked.connect(lambda: self._edit_period())
        del_period = QPushButton("Supprimer")
        del_period.clicked.connect(self._delete_period)
        period_box = QGroupBox("Plannings par département (jours non couverts = repos)")
        period_layout = QGridLayout(period_box)
        period_layout.addWidget(self.period_table, 0, 0, 1, 4)
        period_layout.addWidget(add_period, 1, 0)
        period_layout.addWidget(edit_period, 1, 1)
        period_layout.addWidget(del_period, 1, 2)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(shift_box, 1)
        layout.addWidget(period_box, 1)
        return page

    def _holidays_tab(self) -> QWidget:
        self.holiday_table = _table(["Date (JJ/MM/AAAA)", "Libellé", "Chaque année"])
        for h in self.store.holidays():
            self._add_holiday_row(h.day.strftime("%d/%m/%Y"), h.name, h.recurring)
        add = QPushButton("Ajouter")
        add.clicked.connect(lambda: self._add_holiday_row(date.today().strftime("%d/%m/%Y"),
                                                          "", False))
        delete = QPushButton("Supprimer")
        delete.clicked.connect(lambda: self._delete_selected(self.holiday_table))
        note = QLabel("« Chaque année » : même jour et même mois tous les ans (fêtes à date "
                      "fixe). Les fêtes religieuses changent de date : saisissez-les chaque année.")
        note.setWordWrap(True)
        page = QWidget()
        layout = QGridLayout(page)
        layout.addWidget(self.holiday_table, 0, 0, 1, 3)
        layout.addWidget(add, 1, 0)
        layout.addWidget(delete, 1, 1)
        layout.addWidget(note, 2, 0, 1, 3)
        return page

    # -- table helpers -----------------------------------------------------------
    def _add_shift_row(self, code: str, name: str, start: str, end: str) -> None:
        row = self.shift_table.rowCount()
        self.shift_table.insertRow(row)
        for col, value in enumerate((code, name, start, end)):
            self.shift_table.setItem(row, col, QTableWidgetItem(value))

    def _add_holiday_row(self, day: str, name: str, recurring: bool) -> None:
        row = self.holiday_table.rowCount()
        self.holiday_table.insertRow(row)
        self.holiday_table.setItem(row, 0, QTableWidgetItem(day))
        self.holiday_table.setItem(row, 1, QTableWidgetItem(name))
        check = QTableWidgetItem()
        check.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
                       | Qt.ItemFlag.ItemIsSelectable)
        check.setCheckState(Qt.CheckState.Checked if recurring else Qt.CheckState.Unchecked)
        self.holiday_table.setItem(row, 2, check)

    @staticmethod
    def _delete_selected(table: QTableWidget) -> None:
        for row in sorted({i.row() for i in table.selectedIndexes()}, reverse=True):
            table.removeRow(row)

    @staticmethod
    def _cell(table: QTableWidget, row: int, col: int) -> str:
        item = table.item(row, col)
        return item.text().strip() if item else ""

    def _refresh_periods(self) -> None:
        self.period_table.setRowCount(0)
        for p in self._periods:
            row = self.period_table.rowCount()
            self.period_table.insertRow(row)
            season = "Toute l'année"
            if p.valid_from and p.valid_to:
                season = (f"{p.valid_from[1]:02d}/{p.valid_from[0]:02d} → "
                          f"{p.valid_to[1]:02d}/{p.valid_to[0]:02d}")
            values = (p.department, p.name, fr.weekdays_label(p.weekdays),
                      ", ".join(p.shift_codes), season, str(p.priority))
            for col, value in enumerate(values):
                self.period_table.setItem(row, col, QTableWidgetItem(value))

    def _current_shift_codes(self) -> list[tuple[str, str]]:
        return [(self._cell(self.shift_table, r, 0), self._cell(self.shift_table, r, 1))
                for r in range(self.shift_table.rowCount()) if self._cell(self.shift_table, r, 0)]

    def _edit_period(self, new: bool = False) -> None:
        row = self.period_table.currentRow()
        if not new and row < 0:
            return
        dialog = PeriodDialog(self._current_shift_codes(), self._departments,
                              None if new else self._periods[row], self)
        if dialog.exec() and dialog.result_period:
            if new:
                self._periods.append(dialog.result_period)
            else:
                self._periods[row] = dialog.result_period
            self._refresh_periods()

    def _delete_period(self) -> None:
        row = self.period_table.currentRow()
        if row >= 0:
            del self._periods[row]
            self._refresh_periods()

    # -- connection test ---------------------------------------------------------
    def _params_from_form(self, v: dict | None = None) -> DbParams:
        if v is not None:
            return DbParams(v["db_host"], int(v["db_port"]), v["db_name"], v["db_user"],
                            v["timezone"], int(v["db_connect_timeout_sec"]))
        return DbParams(self.db_host.text().strip(), self.db_port.value(),
                        self.db_name.text().strip(), self.db_user.text().strip(),
                        self.timezone.currentText().strip(), self.db_timeout.value())

    def _test_connection(self) -> None:
        if self._runner.is_running(self._test_job):
            return
        try:
            params = self._params_from_form()
            factory = db_repo_factory(params, self.db_password.text() or None)
        except ValueError as exc:
            self._on_test_error(0, str(exc))
            return
        self.test_button.setEnabled(False)
        self.test_result.setStyleSheet("")
        self.test_result.setText("Connexion en cours…")
        self._test_job = self._runner.start(lambda: check_connection(factory))

    def _on_test_done(self, job_id: int, info: object) -> None:
        self.test_button.setEnabled(True)
        self.test_result.setStyleSheet("color: #15803D;")
        self.test_result.setText(
            f"Connexion réussie — PostgreSQL {info['version']}, lecture seule : "
            f"{info['read_only']}, fuseau de session : {info['timezone']}, "
            f"{info['employees']} employés, {info['punches']} pointages.")

    def _on_test_error(self, job_id: int, message: str) -> None:
        self.test_button.setEnabled(True)
        self.test_result.setStyleSheet("color: #B42318;")
        self.test_result.setText(message)

    # -- save --------------------------------------------------------------------
    def collect(self) -> tuple[dict, list[ShiftDef], list[Holiday]]:
        tz = self.timezone.currentText().strip()
        if tz not in available_timezones():
            raise ValueError(f"Fuseau horaire inconnu : {tz}")
        values = {
            "db_host": self.db_host.text().strip(),
            "db_port": self.db_port.value(),
            "db_name": self.db_name.text().strip(),
            "db_user": self.db_user.text().strip(),
            "db_connect_timeout_sec": self.db_timeout.value(),
            "timezone": tz,
            "refresh_interval_sec": self.refresh.value(),
            "excluded_emp_codes": self.excluded.text().strip(),
            "duplicate_window_min": self.dup_window.value(),
            "window_before_start_min": self.before.value(),
            "window_after_end_min": self.after.value(),
        }
        if not values["db_host"] or not values["db_name"] or not values["db_user"]:
            raise ValueError("Hôte, base de données et utilisateur sont obligatoires")
        shifts = []
        for r in range(self.shift_table.rowCount()):
            code = self._cell(self.shift_table, r, 0)
            if not code:
                raise ValueError(f"Équipe ligne {r + 1} : code obligatoire")
            shifts.append(ShiftDef(code, self._cell(self.shift_table, r, 1) or code,
                                   _parse_hm(self._cell(self.shift_table, r, 2)),
                                   _parse_hm(self._cell(self.shift_table, r, 3))))
        holidays = []
        for r in range(self.holiday_table.rowCount()):
            text = self._cell(self.holiday_table, r, 0)
            try:
                day = datetime.strptime(text, "%d/%m/%Y").date()
            except ValueError:
                raise ValueError(f"Jour férié ligne {r + 1} : date invalide « {text} »") from None
            name = self._cell(self.holiday_table, r, 1)
            if not name:
                raise ValueError(f"Jour férié ligne {r + 1} : libellé obligatoire")
            recurring = self.holiday_table.item(r, 2).checkState() == Qt.CheckState.Checked
            holidays.append(Holiday(day, name, recurring))
        return values, shifts, holidays

    def _save(self) -> None:
        try:
            values, shifts, holidays = self.collect()
            self.store.save_schedule(shifts, self._periods, holidays)
            self.store.set_many(values)
        except (ValueError, KeyError) as exc:
            QMessageBox.warning(self, "Paramètres", str(exc))
            return
        try:
            secrets.set_password(self.store.db_params().keyring_account,
                                 self.db_password.text() or None)
        except secrets.SecretStoreError as exc:
            QMessageBox.warning(self, "Mot de passe",
                                f"Impossible d'enregistrer le mot de passe : {exc}")
        self.accept()

    def done(self, result: int) -> None:
        self._runner.wait_all()
        super().done(result)
