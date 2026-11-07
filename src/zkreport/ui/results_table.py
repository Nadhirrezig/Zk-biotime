"""Filter bar + sortable table, shared by the daily and employee pages."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from . import labels_fr as fr
from . import theme
from .table_models import ResultsFilterProxy, ResultsTableModel


class ResultsTable(QWidget):
    filter_changed = pyqtSignal(str)

    def __init__(self, columns: tuple[str, ...], sort_column: int,
                 with_department: bool = True, with_search: bool = True, parent=None):
        super().__init__(parent)
        self.model = ResultsTableModel(columns, self)
        self.proxy = ResultsFilterProxy(self)
        self.proxy.setSourceModel(self.model)

        self.filter_combo = QComboBox()
        for key, label in fr.FILTERS:
            self.filter_combo.addItem(label, key)
        self.filter_combo.currentIndexChanged.connect(self._on_filter_combo)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Filtre :"))
        bar.addWidget(self.filter_combo)
        self.dept_combo = None
        if with_department:
            self.dept_combo = QComboBox()
            self.dept_combo.addItem("Tous les départements", "")
            self.dept_combo.currentIndexChanged.connect(
                lambda _: self.proxy.set_department(self.dept_combo.currentData()))
            bar.addWidget(QLabel("Département :"))
            bar.addWidget(self.dept_combo)
        self.search = None
        if with_search:
            self.search = QLineEdit()
            self.search.setPlaceholderText("Rechercher un employé (nom ou matricule)…")
            self.search.setClearButtonEnabled(True)
            self.search.textChanged.connect(self.proxy.set_text)
            bar.addWidget(self.search, 1)
        else:
            bar.addStretch(1)
        self.count_label = QLabel()
        self.count_label.setStyleSheet(f"color: {theme.TEXT_MUTED};")
        bar.addWidget(self.count_label)
        for signal in (self.proxy.rowsInserted, self.proxy.rowsRemoved,
                       self.proxy.modelReset, self.proxy.layoutChanged):
            signal.connect(self._update_count)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(sort_column, Qt.SortOrder.AscendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(bar)
        layout.addWidget(self.table, 1)
        self._update_count()

    def set_results(self, results) -> None:
        if self.dept_combo is not None:
            current = self.dept_combo.currentData()
            departments = sorted({r.department for r in results if r.department},
                                 key=str.casefold)
            self.dept_combo.blockSignals(True)
            self.dept_combo.clear()
            self.dept_combo.addItem("Tous les départements", "")
            for dept in departments:
                self.dept_combo.addItem(dept, dept)
            self.dept_combo.setCurrentIndex(max(self.dept_combo.findData(current), 0))
            self.dept_combo.blockSignals(False)
            self.proxy.set_department(self.dept_combo.currentData())
        self.model.set_rows(results)
        self._update_count()

    def set_filter(self, mode: str) -> None:
        index = self.filter_combo.findData(mode)
        if index >= 0:
            self.filter_combo.setCurrentIndex(index)

    def visible_rows(self):
        return self.proxy.visible_rows()

    def filter_description(self) -> list[str]:
        """Active filters as text lines for exports."""
        lines = []
        if self.proxy.mode != fr.FILTER_ALL:
            lines.append(f"Filtre : {fr.FILTER_LABELS[self.proxy.mode]}")
        if self.proxy.department:
            lines.append(f"Département : {self.proxy.department}")
        if self.search is not None and self.search.text().strip():
            lines.append(f"Recherche : {self.search.text().strip()}")
        return lines

    def _on_filter_combo(self, _index: int) -> None:
        mode = self.filter_combo.currentData()
        self.proxy.set_mode(mode)
        self.filter_changed.emit(mode)

    def _update_count(self, *args) -> None:
        self.count_label.setText(f"{self.proxy.rowCount()} / {self.model.rowCount()} lignes")
