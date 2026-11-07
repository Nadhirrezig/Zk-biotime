"""Qt models for attendance tables (daily list and employee history)."""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PyQt6.QtGui import QBrush, QColor

from zkreport.engine.models import DayResult, Status

from . import labels_fr as fr
from . import theme

# Column keys
CODE, NAME, DEPT, DATE, WEEKDAY, ARRIVAL, DEPARTURE, COUNT, STATUS = (
    "code", "name", "dept", "date", "weekday", "arrival", "departure", "count", "status")

HEADERS = {
    CODE: "Matricule", NAME: "Nom", DEPT: "Département", DATE: "Date", WEEKDAY: "Jour",
    ARRIVAL: "Arrivée", DEPARTURE: "Départ", COUNT: "Pointages", STATUS: "Statut",
}
DAILY_COLUMNS = (CODE, NAME, DEPT, ARRIVAL, DEPARTURE, COUNT, STATUS)
EMPLOYEE_COLUMNS = (DATE, WEEKDAY, ARRIVAL, DEPARTURE, COUNT, STATUS)
NUMERIC = {COUNT}
CENTERED = {ARRIVAL, DEPARTURE, COUNT, DATE, WEEKDAY}

ROW_FILLS = {Status.SINGLE_PUNCH: theme.ROW_SINGLE, Status.ABSENT: theme.ROW_ABSENT}


def _hm(dt: datetime | None, day) -> str:
    if dt is None:
        return ""
    text = dt.strftime("%H:%M")
    shift = (dt.date() - day).days
    return f"{text} (+{shift}j)" if shift > 0 else f"{text} ({shift}j)" if shift < 0 else text


def _code_key(code: str):
    return (0, int(code), "") if code.isdigit() else (1, 0, code)


def row_fill(r: DayResult) -> str | None:
    return ROW_FILLS.get(r.status)


class ResultsTableModel(QAbstractTableModel):
    def __init__(self, columns: tuple[str, ...], parent=None):
        super().__init__(parent)
        self.columns = columns
        self._rows: list[DayResult] = []

    def set_rows(self, rows) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def row_at(self, row: int) -> DayResult:
        return self._rows[row]

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.columns)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return HEADERS[self.columns[section]]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        r = self._rows[index.row()]
        key = self.columns[index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            return display(r, key)
        if role == Qt.ItemDataRole.UserRole:  # sort key
            return sort_key(r, key)
        if role == Qt.ItemDataRole.BackgroundRole:
            fill = row_fill(r)
            return QBrush(QColor(fill)) if fill else None
        if role == Qt.ItemDataRole.ForegroundRole and r.status in (
                Status.REST, Status.HOLIDAY, Status.LEAVE):
            return QBrush(QColor(theme.TEXT_MUTED))
        if role == Qt.ItemDataRole.ToolTipRole and r.punches:
            return "Pointages : " + ", ".join(t.strftime("%d/%m %H:%M") for t in r.punches)
        if role == Qt.ItemDataRole.TextAlignmentRole and key in CENTERED:
            return Qt.AlignmentFlag.AlignCenter
        return None


def display(r: DayResult, key: str) -> str:
    if key == CODE:
        return r.emp_code
    if key == NAME:
        return fr.employee_label(r.name, r.emp_code)
    if key == DEPT:
        return r.department
    if key == DATE:
        return r.day.strftime("%d/%m/%Y")
    if key == WEEKDAY:
        return fr.WEEKDAYS[r.day.weekday()]
    if key == ARRIVAL:
        return _hm(r.arrival, r.day)
    if key == DEPARTURE:
        return _hm(r.departure, r.day)
    if key == COUNT:
        return str(r.punch_count) if r.punch_count else ""
    if key == STATUS:
        return fr.status_text(r)
    return ""


def sort_key(r: DayResult, key: str):
    if key == CODE:
        return _code_key(r.emp_code)
    if key in (DATE, WEEKDAY):
        return r.day.toordinal()
    if key == ARRIVAL:
        return r.arrival.timestamp() if r.arrival else float("inf")
    if key == DEPARTURE:
        return r.departure.timestamp() if r.departure else float("inf")
    if key == COUNT:
        return r.punch_count
    return display(r, key).casefold()


class ResultsFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = fr.FILTER_ALL
        self._department = ""
        self._text = ""
        self.setSortRole(Qt.ItemDataRole.UserRole)

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def department(self) -> str:
        return self._department

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.invalidateFilter()

    def set_department(self, department: str) -> None:
        self._department = department
        self.invalidateFilter()

    def set_text(self, text: str) -> None:
        self._text = text.strip().casefold()
        self.invalidateFilter()

    def lessThan(self, left, right) -> bool:
        a, b = left.data(self.sortRole()), right.data(self.sortRole())
        try:
            return a < b
        except TypeError:
            return str(a) < str(b)

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        r: DayResult = self.sourceModel().row_at(source_row)
        if self._department and r.department != self._department:
            return False
        if self._text and self._text not in f"{r.emp_code} {r.name}".casefold():
            return False
        return matches_filter(r, self._mode)

    def visible_rows(self) -> list[DayResult]:
        source = self.sourceModel()
        return [source.row_at(self.mapToSource(self.index(i, 0)).row())
                for i in range(self.rowCount())]


def matches_filter(r: DayResult, mode: str) -> bool:
    if mode == fr.FILTER_PRESENT:
        return r.is_present
    if mode == fr.FILTER_TWICE:
        return r.status is Status.COMPLETE
    if mode == fr.FILTER_ONCE:
        return r.status is Status.SINGLE_PUNCH
    if mode == fr.FILTER_ABSENT:
        return r.status is Status.ABSENT
    return True
