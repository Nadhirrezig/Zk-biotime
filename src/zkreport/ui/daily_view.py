"""Daily attendance table with filters."""
from __future__ import annotations

from PyQt6.QtCore import Qt
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
from .table_models import C_NAME, DailyFilterProxy, DailyTableModel


class DailyView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = DailyTableModel(self)
        self.proxy = DailyFilterProxy(self)
        self.proxy.setSourceModel(self.model)

        self.filter_combo = QComboBox()
        for key, label in fr.FILTERS:
            self.filter_combo.addItem(label, key)
        self.filter_combo.currentIndexChanged.connect(
            lambda _: self.proxy.set_mode(self.filter_combo.currentData()))

        self.dept_combo = QComboBox()
        self.dept_combo.addItem("Tous les départements", "")
        self.dept_combo.currentIndexChanged.connect(
            lambda _: self.proxy.set_department(self.dept_combo.currentData()))

        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher (nom ou matricule)…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.proxy.set_text)

        self.count_label = QLabel()
        self.proxy.rowsInserted.connect(self._update_count)
        self.proxy.rowsRemoved.connect(self._update_count)
        self.proxy.modelReset.connect(self._update_count)
        self.proxy.layoutChanged.connect(self._update_count)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Filtre :"))
        filters.addWidget(self.filter_combo)
        filters.addWidget(QLabel("Département :"))
        filters.addWidget(self.dept_combo)
        filters.addWidget(self.search, 1)
        filters.addWidget(self.count_label)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(C_NAME, Qt.SortOrder.AscendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)

        legend = QLabel(
            "<span style='background:#FFE8A3'>&nbsp;Un seul pointage&nbsp;</span>&nbsp;&nbsp;"
            "<span style='background:#F8D7DA'>&nbsp;Absent&nbsp;</span>&nbsp;&nbsp;"
            "<span style='color:#B42318'>Retard</span>&nbsp;&nbsp;"
            "Survolez une ligne pour voir tous les pointages."
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(filters)
        layout.addWidget(self.table, 1)
        layout.addWidget(legend)
        self._update_count()

    def set_results(self, results) -> None:
        current = self.dept_combo.currentData()
        departments = sorted({r.department for r in results if r.department}, key=str.casefold)
        self.dept_combo.blockSignals(True)
        self.dept_combo.clear()
        self.dept_combo.addItem("Tous les départements", "")
        for dept in departments:
            self.dept_combo.addItem(dept, dept)
        index = self.dept_combo.findData(current)
        self.dept_combo.setCurrentIndex(max(index, 0))
        self.dept_combo.blockSignals(False)
        self.proxy.set_department(self.dept_combo.currentData())
        self.model.set_rows(results)
        self._update_count()

    def set_filter(self, mode: str) -> None:
        index = self.filter_combo.findData(mode)
        if index >= 0:
            self.filter_combo.setCurrentIndex(index)

    def visible_rows(self):
        return [self.model.row_at(self.proxy.mapToSource(self.proxy.index(i, 0)).row())
                for i in range(self.proxy.rowCount())]

    def _update_count(self, *args) -> None:
        self.count_label.setText(f"{self.proxy.rowCount()} / {self.model.rowCount()} lignes")
