"""'Journée' page: date, 4 counts, filtered list, export."""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import QDate, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from zkreport.service import DayCounts, DayReport

from . import labels_fr as fr
from .results_table import ResultsTable
from .stat_cards import DAILY_TITLES, StatCards
from .table_export import ExportBar, snapshot
from .table_models import DAILY_COLUMNS, NAME
from .widgets import date_edit, long_date


class DailyPage(QWidget):
    day_changed = pyqtSignal()
    employee_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.report: DayReport | None = None

        self.date_edit = date_edit(QDate.currentDate())
        self.date_edit.dateChanged.connect(lambda _: self.day_changed.emit())
        prev_day = QPushButton("◀ Veille")
        prev_day.clicked.connect(lambda: self._shift(-1))
        next_day = QPushButton("Lendemain ▶")
        next_day.clicked.connect(lambda: self._shift(1))
        today = QPushButton("Aujourd'hui")
        today.clicked.connect(lambda: self.date_edit.setDate(QDate.currentDate()))
        self.export_bar = ExportBar(self._export_data)

        top = QHBoxLayout()
        top.addWidget(QLabel("Date :"))
        top.addWidget(self.date_edit)
        top.addWidget(prev_day)
        top.addWidget(next_day)
        top.addWidget(today)
        top.addStretch(1)
        top.addWidget(self.export_bar)

        self.cards = StatCards(DAILY_TITLES)
        self.table = ResultsTable(DAILY_COLUMNS, sort_column=DAILY_COLUMNS.index(NAME))
        self.cards.filter_requested.connect(self.table.set_filter)
        self.table.filter_changed.connect(self.cards.set_active_filter)
        self.table.table.doubleClicked.connect(self._open_employee)
        self.table.table.setToolTip("Double-cliquez sur un employé pour voir ses statistiques")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addLayout(top)
        layout.addWidget(self.cards)
        layout.addWidget(self.table, 1)
        self.export_bar.set_enabled(False)

    def _shift(self, days: int) -> None:
        self.date_edit.setDate(self.date_edit.date().addDays(days))

    def _open_employee(self, index) -> None:
        row = self.table.proxy.mapToSource(index).row()
        self.employee_requested.emit(self.table.model.row_at(row).emp_code)

    def selected_day(self) -> date:
        return self.date_edit.date().toPyDate()

    def set_report(self, report: DayReport) -> None:
        self.report = report
        self.counts = DayCounts.from_results(report.results)
        self.cards.set_counts(self.counts)
        self.table.set_results(report.results)
        self.export_bar.set_enabled(True)

    def _export_data(self):
        if self.report is None:
            return None
        c = self.counts
        meta = [
            f"Pointage double : {c.double}   ·   Pointage unique : {c.single}   ·   "
            f"Absents : {c.absent}   ·   Total pointés : {c.total}",
            *self.table.filter_description(),
        ]
        title = f"Présence du {long_date(self.report.day)}"
        return snapshot(self.table.proxy, title, meta), f"presence_{self.report.day.isoformat()}"
