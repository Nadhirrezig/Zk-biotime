"""Four count cards with an icon tile. Each card filters the table below (click again to
clear). Only this file defines the cards' look; the pages use StatCards' API."""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from . import labels_fr as fr
from . import theme as t

CARD_TONES = {
    fr.FILTER_TWICE: t.COMPLETE,
    fr.FILTER_ONCE: t.SINGLE,
    fr.FILTER_ABSENT: t.ABSENT,
    fr.FILTER_PRESENT: t.PRESENT,
}
CARD_ICONS = {
    fr.FILTER_TWICE: "double",
    fr.FILTER_ONCE: "single",
    fr.FILTER_ABSENT: "absent",
    fr.FILTER_PRESENT: "total",
}
HINT_IDLE = "Cliquer pour filtrer"
HINT_ACTIVE = "Filtre actif · cliquer pour retirer"


class IconTile(QWidget):
    """Rounded tinted square with a painted glyph (no font or emoji dependency)."""

    def __init__(self, kind: str, tone: t.Tone, parent=None):
        super().__init__(parent)
        self._kind = kind
        self._tone = tone
        self._selected = False
        self.setFixedSize(44, 44)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        # The selected card is already tinted: a solid tile keeps the icon standing out.
        p.setBrush(QColor(self._tone.solid if self._selected else self._tone.tint))
        p.drawRoundedRect(QRectF(0, 0, 44, 44), 11, 11)
        colour = QColor("#FFFFFF" if self._selected else self._tone.text)
        pen = QPen(colour, 2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.translate(13, 13)  # glyphs are drawn in an 18x18 box
        getattr(self, f"_draw_{self._kind}")(p, colour)

    @staticmethod
    def _draw_double(p: QPainter, c: QColor) -> None:
        # In and out: arrow right on top, arrow left below.
        p.drawLine(QPointF(2, 5.5), QPointF(15, 5.5))
        p.drawPolyline([QPointF(11.5, 2), QPointF(15, 5.5), QPointF(11.5, 9)])
        p.drawLine(QPointF(16, 12.5), QPointF(3, 12.5))
        p.drawPolyline([QPointF(6.5, 9), QPointF(3, 12.5), QPointF(6.5, 16)])

    @staticmethod
    def _draw_single(p: QPainter, c: QColor) -> None:
        # Half-filled circle: one of the two punches.
        circle = QRectF(1.5, 1.5, 15, 15)
        p.drawEllipse(circle)
        p.setBrush(c)
        p.drawPie(circle, 90 * 16, 180 * 16)

    @staticmethod
    def _draw_absent(p: QPainter, c: QColor) -> None:
        p.drawEllipse(QRectF(1.5, 1.5, 15, 15))
        p.drawLine(QPointF(6, 6), QPointF(12, 12))
        p.drawLine(QPointF(12, 6), QPointF(6, 12))

    @staticmethod
    def _draw_total(p: QPainter, c: QColor) -> None:
        p.drawEllipse(QRectF(1.5, 1.5, 15, 15))
        p.drawPolyline([QPointF(5.5, 9.3), QPointF(8, 11.8), QPointF(12.8, 6.6)])


class StatCard(QFrame):
    activated = pyqtSignal(str)

    def __init__(self, filter_key: str, title: str, tone: t.Tone, parent=None):
        super().__init__(parent)
        self.filter_key = filter_key
        self.tone = tone
        self._selected = False
        self._value: int | None = None
        self.setObjectName("statCard")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip(f"{title} : cliquez pour n'afficher que ces lignes")

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(16, 24, 40, 22))
        self.setGraphicsEffect(shadow)

        self.tile = IconTile(CARD_ICONS[filter_key], tone)
        self.title = QLabel(title)
        self.value = QLabel("–")
        self.hint = QLabel(HINT_IDLE)

        texts = QVBoxLayout()
        texts.setSpacing(0)
        texts.addWidget(self.title)
        texts.addWidget(self.value)
        texts.addWidget(self.hint)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)
        layout.addWidget(self.tile, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(texts, 1)
        self._restyle()

    def set_value(self, value: int | None) -> None:
        self._value = value
        self.value.setText("–" if value is None else str(value))
        self._restyle()

    def set_selected(self, selected: bool) -> None:
        if selected != self._selected:
            self._selected = selected
            self.tile.set_selected(selected)
            self.hint.setText(HINT_ACTIVE if selected else HINT_IDLE)
            self._restyle()

    def is_selected(self) -> bool:
        return self._selected

    def _restyle(self) -> None:
        tone = self.tone
        border = tone.solid if self._selected else t.BORDER
        background = tone.tint if self._selected else t.SURFACE
        hover = tone.solid if self._selected else t.BORDER_HOVER
        self.setStyleSheet(
            f"#statCard {{ background: {background}; border: 1px solid {border};"
            f" border-radius: 14px; }}"
            f"#statCard:hover {{ border-color: {hover}; }}"
            f"#statCard:focus {{ border-color: {t.FOCUS}; }}"
            "#statCard QLabel { background: transparent; }"
        )
        accent = tone.text if self._selected else t.TEXT_MUTED
        self.title.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {accent};")
        number = tone.text if self._value else "#98A2B3"
        self.value.setStyleSheet(f"font-size: 28px; font-weight: 700; color: {number};")
        hint = tone.text if self._selected else "#98A2B3"
        self.hint.setStyleSheet(f"font-size: 11px; color: {hint};")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
                event.position().toPoint()):
            self.activated.emit(self.filter_key)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.activated.emit(self.filter_key)
            return
        super().keyPressEvent(event)


class StatCards(QWidget):
    """Row of cards: Pointage double, Pointage unique, Absents, Total pointés."""

    filter_requested = pyqtSignal(str)

    def __init__(self, titles: dict[str, str], parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 6)  # room for the soft shadow
        layout.setSpacing(14)
        self.cards: dict[str, StatCard] = {}
        for key, title in titles.items():
            card = StatCard(key, title, CARD_TONES[key])
            card.activated.connect(self._on_activated)
            layout.addWidget(card)
            self.cards[key] = card
        self._active = fr.FILTER_ALL

    def _on_activated(self, key: str) -> None:
        self.filter_requested.emit(fr.FILTER_ALL if key == self._active else key)

    def set_active_filter(self, key: str) -> None:
        self._active = key
        for card in self.cards.values():
            card.set_selected(card.filter_key == key)

    def set_counts(self, counts) -> None:
        """`counts`: service.DayCounts or None."""
        values = {
            fr.FILTER_TWICE: counts.double if counts else None,
            fr.FILTER_ONCE: counts.single if counts else None,
            fr.FILTER_ABSENT: counts.absent if counts else None,
            fr.FILTER_PRESENT: counts.total if counts else None,
        }
        for key, card in self.cards.items():
            card.set_value(values[key])

    def value(self, key: str) -> str:
        return self.cards[key].value.text()


DAILY_TITLES = {
    fr.FILTER_TWICE: "Pointage double",
    fr.FILTER_ONCE: "Pointage unique",
    fr.FILTER_ABSENT: "Absents",
    fr.FILTER_PRESENT: "Total pointés",
}

EMPLOYEE_TITLES = {
    fr.FILTER_TWICE: "Jours pointage double",
    fr.FILTER_ONCE: "Jours pointage unique",
    fr.FILTER_ABSENT: "Absences",
    fr.FILTER_PRESENT: "Total jours pointés",
}
