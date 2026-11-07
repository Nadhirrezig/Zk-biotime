"""'Employé' page: header (employee + export), selectors, card bar = filter, day list."""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QCompleter,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from zkreport.service import EmployeeReport

from . import labels_fr as fr
from . import theme
from .icons import icon
from .results_table import ResultsTable
from .stat_cards import EMPLOYEE_TITLES, FilterCards
from .table_export import ExportMenu, snapshot
from .table_models import DATE, EMPLOYEE_COLUMNS
from .theme import set_role
from .widgets import PageHeader, date_edit, section_label, short_date


class EmployeePage(QWidget):
    selection_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.report: EmployeeReport | None = None

        self.header = PageHeader()
        self.export_button = ExportMenu(self._export_data)
        self.header.actions.addWidget(self.export_button)

        # Selector bar: who + when
        self.employee_combo = QComboBox()
        self.employee_combo.setEditable(True)
        self.employee_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.employee_combo.setMinimumWidth(300)
        self.employee_combo.lineEdit().setPlaceholderText("Rechercher un employé…")
        self.employee_combo.lineEdit().addAction(
            icon("user", theme.TEXT_MUTED), QLineEdit.ActionPosition.LeadingPosition)
        completer = self.employee_combo.completer()
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.employee_combo.currentIndexChanged.connect(lambda _: self._changed())

        today = QDate.currentDate()
        self.from_edit = date_edit(QDate(today.year(), today.month(), 1))
        self.to_edit = date_edit(today)
        self.from_edit.dateChanged.connect(lambda _: self._changed())
        self.to_edit.dateChanged.connect(lambda _: self._changed())
        this_month = QPushButton("Ce mois")
        last_month = QPushButton("Mois précédent")
        for button, offset in ((this_month, 0), (last_month, -1)):
            set_role(button, "chip")
            button.clicked.connect(lambda _=False, o=offset: self._month(o))

        selectors = QFrame()
        selectors.setObjectName("selectors")
        selectors.setStyleSheet(f"#selectors {{ background: {theme.SURFACE};"
                                f" border: 1px solid {theme.BORDER}; border-radius: 12px; }}")
        row = QHBoxLayout(selectors)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(8)
        row.addWidget(section_label("EMPLOYÉ"))
        row.addWidget(self.employee_combo, 2)
        row.addSpacing(16)
        row.addWidget(section_label("PÉRIODE"))
        row.addWidget(self.from_edit)
        row.addWidget(QLabel("→"))
        row.addWidget(self.to_edit)
        row.addSpacing(6)
        row.addWidget(this_month)
        row.addWidget(last_month)
        row.addStretch(1)

        self.cards = FilterCards(EMPLOYEE_TITLES)
        self.table = ResultsTable(EMPLOYEE_COLUMNS, sort_column=EMPLOYEE_COLUMNS.index(DATE),
                                  with_department=False, with_search=False)
        self.cards.filter_requested.connect(self.table.set_filter)
        self.table.filter_changed.connect(self.cards.set_active_filter)

        # Empty state until an employee is chosen
        self.empty = QLabel("Choisissez un employé et une période\npour voir ses pointages.")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 14px;"
                                 f" background: {theme.SURFACE}; border: 1px dashed {theme.BORDER_STRONG};"
                                 " border-radius: 12px;")
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)
        content_layout.addWidget(self.cards)
        content_layout.addWidget(self.table, 1)
        self.body = QStackedLayout()
        self.body.addWidget(self.empty)
        self.body.addWidget(content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(self.header)
        layout.addWidget(selectors)
        layout.addLayout(self.body, 1)
        self.export_button.set_enabled(False)
        self._update_title()

    # -- selection -------------------------------------------------------------
    def _changed(self) -> None:
        self._update_title()
        self.selection_changed.emit()

    def _update_title(self) -> None:
        index = self.employee_combo.currentIndex()
        name = self.employee_combo.itemText(index).split(" – ", 1)[-1] if index >= 0 \
            else "Fiche employé"
        period = f"Du {short_date(self.from_edit.date().toPyDate())} au " \
                 f"{short_date(self.to_edit.date().toPyDate())}"
        self.header.set_text(name, period if index >= 0 else "Pointages d'un employé sur une période")

    def _month(self, offset: int) -> None:
        anchor = QDate.currentDate().addMonths(offset)
        first = QDate(anchor.year(), anchor.month(), 1)
        last = QDate.currentDate() if offset == 0 else first.addMonths(1).addDays(-1)
        for edit, value in ((self.from_edit, first), (self.to_edit, last)):
            edit.blockSignals(True)
            edit.setDate(value)
            edit.blockSignals(False)
        self._changed()

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

    # -- data ------------------------------------------------------------------
    def set_report(self, report: EmployeeReport) -> None:
        self.report = report
        self.body.setCurrentIndex(1)
        self.cards.set_counts(report.counts, len(report.results))
        self.table.set_results(report.results)
        self.export_button.set_enabled(True)

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
