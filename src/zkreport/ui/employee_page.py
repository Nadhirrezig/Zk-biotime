"""'Employé' page: one employee over a period, 4 counts, day-by-day list, export."""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QCompleter,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from zkreport.service import EmployeeReport

from . import labels_fr as fr
from . import theme
from .results_table import ResultsTable
from .stat_cards import EMPLOYEE_TITLES, StatCards
from .table_export import ExportBar, snapshot
from .table_models import DATE, EMPLOYEE_COLUMNS
from .widgets import date_edit, short_date


class EmployeePage(QWidget):
    selection_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.report: EmployeeReport | None = None

        self.employee_combo = QComboBox()
        self.employee_combo.setEditable(True)
        self.employee_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.employee_combo.setMinimumWidth(280)
        self.employee_combo.lineEdit().setPlaceholderText("Choisir un employé…")
        completer = self.employee_combo.completer()
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.employee_combo.currentIndexChanged.connect(lambda _: self.selection_changed.emit())

        today = QDate.currentDate()
        self.from_edit = date_edit(QDate(today.year(), today.month(), 1))
        self.to_edit = date_edit(today)
        self.from_edit.dateChanged.connect(lambda _: self.selection_changed.emit())
        self.to_edit.dateChanged.connect(lambda _: self.selection_changed.emit())
        this_month = QPushButton("Ce mois")
        this_month.clicked.connect(lambda: self._month(0))
        last_month = QPushButton("Mois précédent")
        last_month.clicked.connect(lambda: self._month(-1))
        self.export_bar = ExportBar(self._export_data)

        top = QHBoxLayout()
        top.addWidget(QLabel("Employé :"))
        top.addWidget(self.employee_combo)
        top.addWidget(QLabel("Du"))
        top.addWidget(self.from_edit)
        top.addWidget(QLabel("au"))
        top.addWidget(self.to_edit)
        top.addWidget(this_month)
        top.addWidget(last_month)
        top.addStretch(1)
        top.addWidget(self.export_bar)

        self.hint = QLabel("Choisissez un employé pour voir ses statistiques sur la période.")
        self.hint.setStyleSheet(f"color: {theme.TEXT_MUTED};")
        self.cards = StatCards(EMPLOYEE_TITLES)
        self.table = ResultsTable(EMPLOYEE_COLUMNS, sort_column=EMPLOYEE_COLUMNS.index(DATE),
                                  with_department=False, with_search=False)
        self.cards.filter_requested.connect(self.table.set_filter)
        self.table.filter_changed.connect(self.cards.set_active_filter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addLayout(top)
        layout.addWidget(self.hint)
        layout.addWidget(self.cards)
        layout.addWidget(self.table, 1)
        self.export_bar.set_enabled(False)

    def _month(self, offset: int) -> None:
        anchor = QDate.currentDate().addMonths(offset)
        first = QDate(anchor.year(), anchor.month(), 1)
        last = first.addMonths(1).addDays(-1)
        if offset == 0:
            last = QDate.currentDate()
        for edit, value in ((self.from_edit, first), (self.to_edit, last)):
            edit.blockSignals(True)
            edit.setDate(value)
            edit.blockSignals(False)
        self.selection_changed.emit()

    def set_employees(self, employees: list[tuple[str, str]]) -> None:
        """[(emp_code, label)], keeps the current selection."""
        current = self.selected_code()
        self.employee_combo.blockSignals(True)
        self.employee_combo.clear()
        for code, label in employees:
            self.employee_combo.addItem(f"{code} – {label}", code)
        index = self.employee_combo.findData(current) if current else -1
        self.employee_combo.setCurrentIndex(index)
        if index < 0:
            self.employee_combo.setEditText("")
        self.employee_combo.blockSignals(False)

    def select_employee(self, emp_code: str) -> None:
        index = self.employee_combo.findData(emp_code)
        if index >= 0:
            self.employee_combo.setCurrentIndex(index)

    def selected_code(self) -> str | None:
        index = self.employee_combo.currentIndex()
        return self.employee_combo.itemData(index) if index >= 0 else None

    def selection(self) -> tuple[str, date, date] | None:
        code = self.selected_code()
        if not code:
            return None
        return code, self.from_edit.date().toPyDate(), self.to_edit.date().toPyDate()

    def set_report(self, report: EmployeeReport) -> None:
        self.report = report
        self.hint.hide()
        self.cards.set_counts(report.counts)
        self.table.set_results(report.results)
        self.export_bar.set_enabled(True)

    def _export_data(self):
        r = self.report
        if r is None or r.employee is None:
            return None
        e, c = r.employee, r.counts
        title = f"{fr.employee_label(e.full_name, e.emp_code)} (matricule {e.emp_code})"
        meta = [
            f"Département : {e.department or '—'}",
            f"Période : du {short_date(r.date_from)} au {short_date(r.date_to)}",
            f"Jours pointage double : {c.double}   ·   Jours pointage unique : {c.single}   ·   "
            f"Absences : {c.absent}   ·   Total jours pointés : {c.total}",
            *self.table.filter_description(),
        ]
        base = f"employe_{e.emp_code}_{r.date_from.isoformat()}_{r.date_to.isoformat()}"
        return snapshot(self.table.proxy, title, meta), base
