"""Qt models for the daily attendance table."""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PyQt6.QtGui import QBrush, QColor

from zkreport.engine.models import DayResult, Missing, Status

from . import labels_fr as fr
from . import theme

COLUMNS = [
    "Matricule", "Nom", "Département", "Horaire", "Arrivée", "Départ", "Pointages",
    "Statut", "Anomalie", "Retard (min)", "Départ anticipé (min)", "Heures travaillées",
    "Heures sup.",
]
C_CODE, C_NAME, C_DEPT, C_SHIFT, C_IN, C_OUT, C_COUNT, C_STATUS, C_ANOMALY, C_LATE, \
    C_EARLY, C_WORKED, C_OT = range(len(COLUMNS))

BG_SINGLE = QColor(theme.ROW_SINGLE)
BG_ABSENT = QColor(theme.ROW_ABSENT)
FG_LATE = QColor(theme.LATE.text)
FG_MUTED = QColor(theme.TEXT_MUTED)


def _hm(dt: datetime | None, day) -> str:
    if dt is None:
        return ""
    text = dt.strftime("%H:%M")
    shift = (dt.date() - day).days
    return f"{text} (+{shift}j)" if shift > 0 else f"{text} ({shift}j)" if shift < 0 else text


def _code_key(code: str):
    return (0, int(code), "") if code.isdigit() else (1, 0, code)


class DailyTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
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
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        r = self._rows[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(r, col)
        if role == Qt.ItemDataRole.UserRole:  # sort key
            return self._sort_key(r, col)
        if role == Qt.ItemDataRole.BackgroundRole:
            if r.status is Status.SINGLE_PUNCH:
                return QBrush(BG_SINGLE)
            if r.status is Status.ABSENT:
                return QBrush(BG_ABSENT)
        if role == Qt.ItemDataRole.ForegroundRole:
            if col in (C_LATE, C_IN) and r.is_late:
                return QBrush(FG_LATE)
            if r.status in (Status.REST, Status.HOLIDAY, Status.LEAVE):
                return QBrush(FG_MUTED)
        if role == Qt.ItemDataRole.ToolTipRole:
            if r.punches:
                return "Pointages : " + ", ".join(t.strftime("%d/%m %H:%M") for t in r.punches)
            if r.holiday_name:
                return r.holiday_name
        if role == Qt.ItemDataRole.TextAlignmentRole and col in (C_COUNT, C_LATE, C_EARLY,
                                                                  C_WORKED, C_OT, C_IN, C_OUT):
            return Qt.AlignmentFlag.AlignCenter
        return None

    def _display(self, r: DayResult, col: int):
        if col == C_CODE:
            return r.emp_code
        if col == C_NAME:
            return fr.employee_label(r.name, r.emp_code)
        if col == C_DEPT:
            return r.department
        if col == C_SHIFT:
            if r.scheduled_start and r.scheduled_end:
                return (f"{r.shift_name} {r.scheduled_start:%H:%M}–{r.scheduled_end:%H:%M}")
            return r.shift_name or ""
        if col == C_IN:
            return _hm(r.arrival, r.day)
        if col == C_OUT:
            return _hm(r.departure, r.day)
        if col == C_COUNT:
            return str(r.punch_count) if r.punch_count else ""
        if col == C_STATUS:
            label = fr.STATUS[r.status]
            return f"{label} ({r.holiday_name})" if r.status is Status.HOLIDAY and r.holiday_name \
                else label
        if col == C_ANOMALY:
            parts = [fr.MISSING[r.missing]] if r.missing is not Missing.NONE else []
            if r.unscheduled:
                parts.append("Hors planning")
            if r.holiday_name and r.is_present:
                parts.append(f"Travail jour férié ({r.holiday_name})")
            return " · ".join(parts)
        if col == C_LATE:
            return str(r.late_min) if r.late_min else ""
        if col == C_EARLY:
            return str(r.early_leave_min) if r.early_leave_min else ""
        if col == C_WORKED:
            return fr.minutes_hm(r.worked_min)
        if col == C_OT:
            return fr.minutes_hm(r.overtime_min)
        return None

    def _sort_key(self, r: DayResult, col: int):
        if col == C_CODE:
            return _code_key(r.emp_code)
        if col == C_IN:
            return r.arrival.timestamp() if r.arrival else float("inf")
        if col == C_OUT:
            return r.departure.timestamp() if r.departure else float("inf")
        if col == C_COUNT:
            return r.punch_count
        if col == C_LATE:
            return r.late_min
        if col == C_EARLY:
            return r.early_leave_min
        if col == C_WORKED:
            return r.worked_min
        if col == C_OT:
            return r.overtime_min
        return str(self._display(r, col) or "").casefold()


class DailyFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = fr.FILTER_ALL
        self._department = ""
        self._text = ""
        self.setSortRole(Qt.ItemDataRole.UserRole)

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


def matches_filter(r: DayResult, mode: str) -> bool:
    if mode == fr.FILTER_PRESENT:
        return r.is_present
    if mode == fr.FILTER_TWICE:
        return r.status is Status.COMPLETE
    if mode == fr.FILTER_ONCE:
        return r.status is Status.SINGLE_PUNCH
    if mode == fr.FILTER_ABSENT:
        return r.status is Status.ABSENT
    if mode == fr.FILTER_LATE:
        return r.is_late
    return True
