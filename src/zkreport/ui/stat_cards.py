"""Four basic count cards. Each card filters the table below (click again to clear)."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from . import labels_fr as fr
from . import theme as t

# (filter key, tone)
CARD_TONES = {
    fr.FILTER_TWICE: t.COMPLETE,
    fr.FILTER_ONCE: t.SINGLE,
    fr.FILTER_ABSENT: t.ABSENT,
    fr.FILTER_PRESENT: t.PRESENT,
}


class StatCard(QFrame):
    activated = pyqtSignal(str)

    def __init__(self, filter_key: str, title: str, tone: t.Tone, parent=None):
        super().__init__(parent)
        self.filter_key = filter_key
        self.tone = tone
        self._selected = False
        self.setObjectName("statCard")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip("Cliquez pour filtrer le tableau")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(2)
        self.title = QLabel(title)
        self.title.setStyleSheet(f"font-size: 13px; color: {t.TEXT_MUTED}; background: transparent;")
        self.value = QLabel("–")
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        self.set_value(None)
        self._restyle()

    def set_value(self, value: int | None) -> None:
        self.value.setText("–" if value is None else str(value))
        colour = self.tone.text if value else t.TEXT_MUTED
        self.value.setStyleSheet(f"font-size: 30px; font-weight: 600; color: {colour};"
                                 f" background: transparent;")

    def set_selected(self, selected: bool) -> None:
        if selected != self._selected:
            self._selected = selected
            self._restyle()

    def is_selected(self) -> bool:
        return self._selected

    def _restyle(self) -> None:
        border = self.tone.solid if self._selected else t.BORDER
        background = self.tone.tint if self._selected else t.SURFACE
        self.setStyleSheet(
            f"#statCard {{ background: {background}; border: 1px solid {border};"
            f" border-top: 3px solid {self.tone.solid}; border-radius: 8px; }}"
            f"#statCard:hover {{ border-color: {t.BORDER_HOVER}; border-top-color: {self.tone.solid}; }}"
            f"#statCard:focus {{ border-color: {t.FOCUS}; border-top-color: {self.tone.solid}; }}"
        )

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
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
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
