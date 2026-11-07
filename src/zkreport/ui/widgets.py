"""Shared widgets: page header, date stepper, French date formatting."""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import QDate, QLocale, Qt, pyqtSignal
from PyQt6.QtWidgets import QDateEdit, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import theme
from .icons import icon
from .theme import set_role

FRENCH = QLocale(QLocale.Language.French, QLocale.Country.Tunisia)


def date_edit(value: QDate, fmt: str = "dd/MM/yyyy") -> QDateEdit:
    edit = QDateEdit()
    edit.setCalendarPopup(True)
    edit.setLocale(FRENCH)
    edit.setDisplayFormat(fmt)
    edit.setDate(value)
    edit.setMinimumWidth(124)
    return edit


def long_date(day: date) -> str:
    return FRENCH.toString(QDate(day.year, day.month, day.day), "dddd d MMMM yyyy")


def title_date(day: date) -> str:
    text = long_date(day)
    return text[:1].upper() + text[1:]


def short_date(day: date) -> str:
    return day.strftime("%d/%m/%Y")


class PageHeader(QWidget):
    """Large title + muted subtitle on the left, actions on the right."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.title = QLabel()
        self.title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {theme.TEXT};")
        self.subtitle = QLabel()
        self.subtitle.setStyleSheet(f"font-size: 13px; color: {theme.TEXT_MUTED};")
        texts.addWidget(self.title)
        texts.addWidget(self.subtitle)
        layout.addLayout(texts)
        layout.addStretch(1)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(8)
        layout.addLayout(self.actions)

    def set_text(self, title: str, subtitle: str = "") -> None:
        self.title.setText(title)
        self.subtitle.setText(subtitle)


class DateStepper(QWidget):
    """[‹] [date] [›] joined into one control, plus an 'Aujourd'hui' link."""

    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.prev_button = QPushButton()
        self.next_button = QPushButton()
        for button, kind, tip, delta in ((self.prev_button, "chevron-left", "Jour précédent", -1),
                                         (self.next_button, "chevron-right", "Jour suivant", 1)):
            button.setIcon(icon(kind, theme.TEXT_SECONDARY))
            button.setToolTip(tip)
            set_role(button, "stepper")
            button.clicked.connect(lambda _=False, d=delta: self.step(d))
        self.edit = date_edit(QDate.currentDate())
        self.edit.dateChanged.connect(lambda _: self.changed.emit())
        # Join the three controls visually: square inner corners.
        self.prev_button.setStyleSheet("border-top-right-radius: 0; border-bottom-right-radius: 0;")
        self.next_button.setStyleSheet("border-top-left-radius: 0; border-bottom-left-radius: 0;")
        self.edit.setStyleSheet("QDateEdit { border-radius: 0; border-left: none;"
                                " border-right: none; }")
        self.today_button = QPushButton("Aujourd'hui")
        set_role(self.today_button, "ghost")
        self.today_button.clicked.connect(lambda: self.edit.setDate(QDate.currentDate()))
        layout.addWidget(self.prev_button)
        layout.addWidget(self.edit)
        layout.addWidget(self.next_button)
        layout.addSpacing(6)
        layout.addWidget(self.today_button)

    def step(self, days: int) -> None:
        self.edit.setDate(self.edit.date().addDays(days))

    def day(self) -> date:
        return self.edit.date().toPyDate()

    def set_day(self, day: date) -> None:
        self.edit.setDate(QDate(day.year, day.month, day.day))


def section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 12px; font-weight: 600;")
    label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
    return label
