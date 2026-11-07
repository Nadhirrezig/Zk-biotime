"""Search/department bar + sortable table with status pills. Filter mode comes from the
card bar (FilterCards) through `set_filter`."""
from __future__ import annotations

from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QStyle,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from zkreport.engine.models import Status

from . import labels_fr as fr
from . import theme
from .icons import icon
from .table_models import RESULT_ROLE, STATUS, ResultsFilterProxy, ResultsTableModel

PILL_TONES = {
    Status.COMPLETE: theme.DOUBLE,
    Status.SINGLE_PUNCH: theme.SINGLE,
    Status.ABSENT: theme.ABSENT,
}


def _draw_row_base(painter: QPainter, option, selected: bool) -> None:
    if selected:
        painter.fillRect(option.rect, QColor(theme.ACCENT_TINT))
    painter.setPen(QPen(QColor(theme.DIVIDER), 1))
    painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())


class StatusPillDelegate(QStyledItemDelegate):
    """Status as a rounded pill: coloured dot + label (grey for repos/férié/congé)."""

    def paint(self, painter: QPainter, option, index) -> None:
        r = index.data(RESULT_ROLE)
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        _draw_row_base(painter, option, bool(option.state & QStyle.StateFlag.State_Selected))
        tone = PILL_TONES.get(r.status, theme.OTHER) if r else theme.OTHER
        font = QFont(option.font)
        font.setPixelSize(12)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        metrics = painter.fontMetrics()  # measure with the font actually used to draw
        width = min(metrics.horizontalAdvance(text) + 36, option.rect.width() - 16)
        pill = QRectF(option.rect.left() + 10, option.rect.center().y() - 11, width, 22)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tone.tint))
        painter.drawRoundedRect(pill, 11, 11)
        painter.setBrush(QColor(tone.solid))
        painter.drawEllipse(QRectF(pill.left() + 10, pill.center().y() - 3, 6, 6))
        painter.setPen(QColor(tone.text))
        text_rect = pill.adjusted(22, 0, -6, 0)
        if metrics.horizontalAdvance(text) > text_rect.width():
            text = metrics.elidedText(text, Qt.TextElideMode.ElideRight, int(text_rect.width()))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         text)
        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        base = super().sizeHint(option, index)
        return QSize(base.width() + 40, base.height())


class ResultsTable(QWidget):
    filter_changed = pyqtSignal(str)

    def __init__(self, columns: tuple[str, ...], sort_column: int,
                 with_department: bool = True, with_search: bool = True, parent=None):
        super().__init__(parent)
        self.model = ResultsTableModel(columns, self)
        self.proxy = ResultsFilterProxy(self)
        self.proxy.setSourceModel(self.model)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.search = None
        if with_search:
            self.search = QLineEdit()
            self.search.setPlaceholderText("Rechercher un employé (nom ou matricule)")
            self.search.setClearButtonEnabled(True)
            self.search.addAction(icon("search", theme.TEXT_MUTED),
                                  QLineEdit.ActionPosition.LeadingPosition)
            self.search.setMaximumWidth(360)
            self.search.textChanged.connect(self.proxy.set_text)
            bar.addWidget(self.search, 1)
        self.dept_combo = None
        if with_department:
            self.dept_combo = QComboBox()
            self.dept_combo.addItem("Tous les départements", "")
            self.dept_combo.setMinimumWidth(200)
            self.dept_combo.currentIndexChanged.connect(
                lambda _: self.proxy.set_department(self.dept_combo.currentData()))
            bar.addWidget(self.dept_combo)
        bar.addStretch(1)
        self.count_label = QLabel()
        self.count_label.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 12px;")
        bar.addWidget(self.count_label)
        for signal in (self.proxy.rowsInserted, self.proxy.rowsRemoved,
                       self.proxy.modelReset, self.proxy.layoutChanged):
            signal.connect(self._update_count)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(sort_column, Qt.SortOrder.AscendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setItemDelegateForColumn(columns.index(STATUS), StatusPillDelegate(self.table))
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        header.setHighlightSections(False)
        header.setMinimumSectionSize(80)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        if with_search or with_department:
            layout.addLayout(bar)
        else:
            self.count_label.hide()
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
        if mode != self.proxy.mode:
            self.proxy.set_mode(mode)
        self.filter_changed.emit(mode)

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

    def _update_count(self, *args) -> None:
        shown, total = self.proxy.rowCount(), self.model.rowCount()
        self.count_label.setText(f"{shown} ligne{'s' if shown > 1 else ''}" if shown == total
                                 else f"{shown} sur {total} lignes")
