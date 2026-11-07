"""Small shared widgets and French date formatting."""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import QDate, QLocale
from PyQt6.QtWidgets import QDateEdit

FRENCH = QLocale(QLocale.Language.French, QLocale.Country.Tunisia)


def date_edit(value: QDate) -> QDateEdit:
    edit = QDateEdit()
    edit.setCalendarPopup(True)
    edit.setLocale(FRENCH)
    edit.setDisplayFormat("dddd dd/MM/yyyy")
    edit.setDate(value)
    return edit


def long_date(day: date) -> str:
    return FRENCH.toString(QDate(day.year, day.month, day.day), "dddd d MMMM yyyy")


def short_date(day: date) -> str:
    return day.strftime("%d/%m/%Y")
