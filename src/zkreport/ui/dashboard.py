"""Dashboard: count cards for the chosen date. Clicking a card filters the table."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from zkreport.engine import Summary

from . import labels_fr as fr

CARDS = [
    # (key, label, filter, accent colour)
    ("employees", "Effectif", fr.FILTER_ALL, "#374151"),
    ("present", "Présents", fr.FILTER_PRESENT, "#15803D"),
    ("complete", "Deux pointages", fr.FILTER_TWICE, "#1D4ED8"),
    ("single_punch", "Un seul pointage", fr.FILTER_ONCE, "#B45309"),
    ("late", "En retard", fr.FILTER_LATE, "#B42318"),
    ("absent", "Absents", fr.FILTER_ABSENT, "#9F1239"),
    ("holiday", "Férié", fr.FILTER_ALL, "#6B7280"),
    ("rest", "Repos", fr.FILTER_ALL, "#6B7280"),
]


class _Card(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, label: str, filter_key: str, colour: str, parent=None):
        super().__init__(parent)
        self._filter = filter_key
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"#card {{ border: 1px solid #D1D5DB; border-left: 4px solid {colour};"
            f" border-radius: 6px; background: palette(base); }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        self.value = QLabel("–")
        self.value.setStyleSheet(f"font-size: 24px; font-weight: 600; color: {colour};")
        caption = QLabel(label)
        caption.setStyleSheet("color: palette(text);")
        layout.addWidget(self.value)
        layout.addWidget(caption)

    def mousePressEvent(self, event):
        self.clicked.emit(self._filter)
        super().mousePressEvent(event)


class Dashboard(QWidget):
    filter_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._cards: dict[str, _Card] = {}
        for key, label, filter_key, colour in CARDS:
            card = _Card(label, filter_key, colour)
            card.clicked.connect(self.filter_requested)
            layout.addWidget(card)
            self._cards[key] = card

    def set_summary(self, summary: Summary | None) -> None:
        for key, card in self._cards.items():
            card.value.setText("–" if summary is None else str(getattr(summary, key)))

    def value(self, key: str) -> str:
        return self._cards[key].value.text()
