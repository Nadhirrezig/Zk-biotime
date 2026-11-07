"""'Journée' page: header (date + export), card bar = filter, search, list."""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from zkreport.service import DayCounts, DayReport

from .results_table import ResultsTable
from .stat_cards import DAILY_TITLES, FilterCards
from .table_export import ExportMenu, snapshot
from .table_models import DAILY_COLUMNS, NAME
from .widgets import DateStepper, PageHeader, long_date, title_date


class DailyPage(QWidget):
    day_changed = pyqtSignal()
    employee_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.report: DayReport | None = None
        self.counts: DayCounts | None = None

        self.header = PageHeader()
        self.stepper = DateStepper()
        self.stepper.changed.connect(self._on_day_changed)
        self.export_button = ExportMenu(self._export_data)
        self.header.actions.addWidget(self.stepper)
        self.header.actions.addSpacing(8)
        self.header.actions.addWidget(self.export_button)

        self.cards = FilterCards(DAILY_TITLES)
        self.table = ResultsTable(DAILY_COLUMNS, sort_column=DAILY_COLUMNS.index(NAME))
        self.cards.filter_requested.connect(self.table.set_filter)
        self.table.filter_changed.connect(self.cards.set_active_filter)
        self.table.table.doubleClicked.connect(self._open_employee)
        self.table.table.setToolTip("Double-cliquez sur un employé pour voir ses statistiques")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(self.header)
        layout.addWidget(self.cards)
        layout.addWidget(self.table, 1)
        self.export_button.set_enabled(False)
        self._update_title()

    @property
    def date_edit(self):
        return self.stepper.edit

    def _on_day_changed(self) -> None:
        self._update_title()
        self.day_changed.emit()

    def _update_title(self) -> None:
        self.header.set_text(title_date(self.selected_day()), "Présence de la journée")

    def _open_employee(self, index) -> None:
        row = self.table.proxy.mapToSource(index).row()
        self.employee_requested.emit(self.table.model.row_at(row).emp_code)

    def selected_day(self) -> date:
        return self.stepper.day()

    def set_report(self, report: DayReport) -> None:
        self.report = report
        self.counts = DayCounts.from_results(report.results)
        self.cards.set_counts(self.counts, len(report.results))
        self.table.set_results(report.results)
        self.export_button.set_enabled(True)

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
