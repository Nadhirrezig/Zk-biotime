"""Card bar that is also the table filter: Tous / Double / Unique / Absents / Pointés.

One joined bar of segments; the selected segment is tinted with its colour and underlined.
Mouse, Enter or Space select a segment; arrow keys move between segments.
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from . import labels_fr as fr
from . import theme as t

TONES = {
    fr.FILTER_ALL: t.ALL,
    fr.FILTER_TWICE: t.DOUBLE,
    fr.FILTER_ONCE: t.SINGLE,
    fr.FILTER_ABSENT: t.ABSENT,
    fr.FILTER_PRESENT: t.PUNCHED,
}
ORDER = (fr.FILTER_ALL, fr.FILTER_TWICE, fr.FILTER_ONCE, fr.FILTER_ABSENT, fr.FILTER_PRESENT)

DAILY_TITLES = {
    fr.FILTER_ALL: "Tous",
    fr.FILTER_TWICE: "Pointage double",
    fr.FILTER_ONCE: "Pointage unique",
    fr.FILTER_ABSENT: "Absents",
    fr.FILTER_PRESENT: "Total pointés",
}
EMPLOYEE_TITLES = {
    fr.FILTER_ALL: "Tous les jours",
    fr.FILTER_TWICE: "Jours double",
    fr.FILTER_ONCE: "Jours unique",
    fr.FILTER_ABSENT: "Absences",
    fr.FILTER_PRESENT: "Jours pointés",
}


class _Dot(QWidget):
    def __init__(self, colour: str, parent=None):
        super().__init__(parent)
        self._colour = colour
        self.setFixedSize(8, 8)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._colour))
        p.drawEllipse(QRectF(0, 0, 8, 8))


class Segment(QFrame):
    activated = pyqtSignal(str)
    step = pyqtSignal(str, int)

    def __init__(self, filter_key: str, title: str, parent=None):
        super().__init__(parent)
        self.filter_key = filter_key
        self.tone = TONES[filter_key]
        self._selected = False
        self._hover = False
        self._count: int | None = None
        self.round_left = False   # first/last segment follow the bar's rounded corners
        self.round_right = False
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(78)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(4)
        head = QHBoxLayout()
        head.setSpacing(7)
        if filter_key != fr.FILTER_ALL:
            head.addWidget(_Dot(self.tone.solid), 0, Qt.AlignmentFlag.AlignVCenter)
        self.title = QLabel(title)
        head.addWidget(self.title)
        head.addStretch(1)
        layout.addLayout(head)
        self.value = QLabel("–")
        layout.addWidget(self.value)
        self._restyle()

    def set_count(self, count: int | None) -> None:
        self._count = count
        self.value.setText("–" if count is None else str(count))
        self._restyle()

    def set_selected(self, selected: bool) -> None:
        if selected != self._selected:
            self._selected = selected
            self._restyle()
            self.update()

    def is_selected(self) -> bool:
        return self._selected

    def _restyle(self) -> None:
        if self._selected:
            number = self.tone.text
        elif self._count:
            number = t.TEXT
        else:
            number = "#98A2B3"
        self.title.setStyleSheet(
            f"background: transparent; font-size: 12px; font-weight: 600;"
            f" color: {self.tone.text if self._selected else t.TEXT_MUTED};")
        self.value.setStyleSheet(
            f"background: transparent; font-size: 28px; font-weight: 700; color: {number};")

    # painting: tint + bottom indicator when selected, soft hover
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        p.setClipPath(self._shape(rect))
        if self._selected:
            p.fillRect(rect, QColor(self.tone.tint))
            p.fillRect(QRectF(rect.left(), rect.bottom() - 2, rect.width(), 3),
                       QColor(self.tone.solid))
        elif self._hover:
            p.fillRect(rect, QColor("#F9FAFB"))
        if self.hasFocus():
            pen = p.pen()
            pen.setColor(QColor(t.FOCUS))
            pen.setWidth(2)
            p.setPen(pen)
            p.drawRect(rect.adjusted(1, 1, -2, -2))
        super().paintEvent(event)

    def _shape(self, rect: QRectF) -> QPainterPath:
        radius = 11.0
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        square = QPainterPath()
        if not self.round_left:
            square.addRect(QRectF(rect.left(), rect.top(), rect.width() / 2, rect.height()))
        if not self.round_right:
            square.addRect(QRectF(rect.center().x(), rect.top(), rect.width() / 2, rect.height()))
        return path.united(square)

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
                event.position().toPoint()):
            self.activated.emit(self.filter_key)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.activated.emit(self.filter_key)
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self.step.emit(self.filter_key, -1 if key == Qt.Key.Key_Left else 1)
        else:
            super().keyPressEvent(event)


class FilterCards(QFrame):
    """The joined bar. `filter_requested(key)` drives the table; `set_active_filter(key)`
    reflects the table's current filter."""

    filter_requested = pyqtSignal(str)

    def __init__(self, titles: dict[str, str], parent=None):
        super().__init__(parent)
        self.setObjectName("filterCards")
        self.setStyleSheet(
            f"#filterCards {{ background: {t.SURFACE}; border: 1px solid {t.BORDER};"
            f" border-radius: 12px; }}")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        self.cards: dict[str, Segment] = {}
        for i, key in enumerate(ORDER):
            if i:
                divider = QFrame()
                divider.setFixedWidth(1)
                divider.setStyleSheet(f"background: {t.DIVIDER}; margin: 14px 0;")
                layout.addWidget(divider)
            segment = Segment(key, titles[key])
            segment.activated.connect(self._on_activated)
            segment.step.connect(self._step)
            layout.addWidget(segment, 1)
            self.cards[key] = segment
        self.cards[ORDER[0]].round_left = True
        self.cards[ORDER[-1]].round_right = True
        self._active = fr.FILTER_ALL
        self.set_active_filter(fr.FILTER_ALL)

    def _on_activated(self, key: str) -> None:
        # Clicking the selected segment again goes back to "Tous".
        self.filter_requested.emit(fr.FILTER_ALL if key == self._active else key)

    def _step(self, key: str, delta: int) -> None:
        index = (ORDER.index(key) + delta) % len(ORDER)
        self.cards[ORDER[index]].setFocus()

    def set_active_filter(self, key: str) -> None:
        self._active = key
        for segment in self.cards.values():
            segment.set_selected(segment.filter_key == key)

    def set_counts(self, counts, rows: int | None) -> None:
        """`counts`: service.DayCounts or None; `rows`: number of lines (Tous)."""
        values = {
            fr.FILTER_ALL: rows,
            fr.FILTER_TWICE: counts.double if counts else None,
            fr.FILTER_ONCE: counts.single if counts else None,
            fr.FILTER_ABSENT: counts.absent if counts else None,
            fr.FILTER_PRESENT: counts.total if counts else None,
        }
        for key, segment in self.cards.items():
            segment.set_count(values[key])

    def value(self, key: str) -> str:
        return self.cards[key].value.text()
