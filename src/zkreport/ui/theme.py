"""Light theme: colour tokens and the application stylesheet."""
from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

# Neutrals
PAGE_BG = "#F5F6F8"
SURFACE = "#FFFFFF"
BORDER = "#E4E7EC"
BORDER_STRONG = "#D0D5DD"
BORDER_HOVER = "#B9C0CC"
TEXT = "#101828"
TEXT_SECONDARY = "#344054"
TEXT_MUTED = "#667085"
DIVIDER = "#EEF0F3"
FOCUS = "#A4BCFD"

# Brand / actions
ACCENT = "#444CE7"
ACCENT_HOVER = "#3538CD"
ACCENT_TINT = "#EEF4FF"

# Sidebar (dark ink)
SIDEBAR_BG = "#0E1525"
SIDEBAR_HOVER = "#182133"
SIDEBAR_ACTIVE = "#212C42"
SIDEBAR_TEXT = "#A3AEC2"
SIDEBAR_TEXT_ACTIVE = "#FFFFFF"
SIDEBAR_MUTED = "#6B778C"


@dataclass(frozen=True)
class Tone:
    """`solid` for dots/bars, `text` for numbers and pill text (AA on white and on `tint`),
    `tint` for selected backgrounds and pills."""
    solid: str
    text: str
    tint: str


DOUBLE = Tone("#12B76A", "#067647", "#ECFDF3")
SINGLE = Tone("#F79009", "#B54708", "#FFFAEB")
ABSENT = Tone("#F04438", "#B42318", "#FEF3F2")
PUNCHED = Tone(ACCENT, ACCENT_HOVER, ACCENT_TINT)
ALL = Tone("#667085", "#344054", "#F2F4F7")
OTHER = Tone("#98A2B3", "#475467", "#F2F4F7")

# Export row fills (Excel/PDF), same hues
ROW_SINGLE = "#FEF0C7"
ROW_ABSENT = "#FEE4E2"


STYLESHEET = f"""
QWidget {{ font-size: 13px; color: {TEXT}; }}
QToolTip {{ background: {TEXT}; color: white; border: none; padding: 4px 8px; }}

/* Buttons: secondary by default, `role` property for primary / ghost / segment */
QPushButton {{
    background: {SURFACE}; color: {TEXT_SECONDARY}; border: 1px solid {BORDER_STRONG};
    border-radius: 8px; padding: 6px 12px; font-weight: 600;
}}
QPushButton:hover {{ background: #F9FAFB; border-color: {BORDER_HOVER}; }}
QPushButton:pressed {{ background: #F2F4F7; }}
QPushButton:focus {{ border-color: {FOCUS}; }}
QPushButton:disabled {{ color: #98A2B3; background: #F9FAFB; border-color: {BORDER}; }}
QPushButton[role="primary"] {{ background: {ACCENT}; color: white; border: 1px solid {ACCENT}; }}
QPushButton[role="primary"]:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton[role="primary"]:disabled {{ background: #C7D7FE; border-color: #C7D7FE; color: white; }}
QPushButton[role="primary"]::menu-indicator {{ width: 0; }}
QPushButton[role="ghost"] {{ background: transparent; border: 1px solid transparent; color: {ACCENT}; }}
QPushButton[role="ghost"]:hover {{ background: {ACCENT_TINT}; }}
QPushButton[role="stepper"] {{ padding: 6px 10px; min-width: 14px; }}
QPushButton[role="chip"] {{
    border-radius: 13px; padding: 3px 12px; min-height: 20px; font-weight: 500;
    color: {TEXT_SECONDARY};
}}
QPushButton[role="chip"]:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}

/* Inputs */
QLineEdit, QComboBox, QDateEdit, QSpinBox {{
    background: {SURFACE}; border: 1px solid {BORDER_STRONG}; border-radius: 8px;
    padding: 5px 10px; min-height: 20px; selection-background-color: {ACCENT_TINT};
    selection-color: {TEXT};
}}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; padding: 4px;
    selection-background-color: {ACCENT_TINT}; selection-color: {TEXT}; outline: 0;
}}

/* Menus */
QMenu {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 7px 28px 7px 12px; border-radius: 6px; color: {TEXT_SECONDARY}; }}
QMenu::item:selected {{ background: {ACCENT_TINT}; color: {ACCENT_HOVER}; }}
QMenu::icon {{ padding-left: 8px; }}
QMenu::separator {{ height: 1px; background: {DIVIDER}; margin: 4px 6px; }}

/* Tables */
QTableView {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px;
    gridline-color: transparent; selection-background-color: {ACCENT_TINT};
    selection-color: {TEXT}; outline: 0;
}}
QTableView::item {{ border-bottom: 1px solid {DIVIDER}; padding: 0 10px; }}
QTableView::item:selected {{ background: {ACCENT_TINT}; color: {TEXT}; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: #F9FAFB; color: {TEXT_MUTED}; border: none; border-bottom: 1px solid {BORDER};
    padding: 9px 10px; font-size: 11px; font-weight: 700;
}}
QTableCornerButton::section {{ background: #F9FAFB; border: none; }}

/* Scrollbars */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: #D0D5DD; border-radius: 3px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px 4px; }}
QScrollBar::handle:horizontal {{ background: #D0D5DD; border-radius: 3px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* Dialog tabs and group boxes (settings) */
QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 10px; background: {SURFACE}; top: -1px; }}
QTabBar::tab {{
    background: transparent; color: {TEXT_MUTED}; padding: 8px 14px; border: none;
    border-bottom: 2px solid transparent; font-weight: 600;
}}
QTabBar::tab:selected {{ color: {ACCENT}; border-bottom-color: {ACCENT}; }}
QTabBar::tab:hover {{ color: {TEXT}; }}
QGroupBox {{ border: 1px solid {BORDER}; border-radius: 10px; margin-top: 14px; padding-top: 10px;
            font-weight: 600; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 4px; color: {TEXT_SECONDARY}; }}
QDialog {{ background: {PAGE_BG}; }}
"""


def apply_light_theme(app: QApplication) -> None:
    """Fusion style, fixed light palette and the app stylesheet, whatever the Windows theme."""
    app.setStyle("Fusion")
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: PAGE_BG,
        QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: SURFACE,
        QPalette.ColorRole.AlternateBase: "#F9FAFB",
        QPalette.ColorRole.Text: TEXT,
        QPalette.ColorRole.Button: SURFACE,
        QPalette.ColorRole.ButtonText: TEXT,
        QPalette.ColorRole.ToolTipBase: TEXT,
        QPalette.ColorRole.ToolTipText: SURFACE,
        QPalette.ColorRole.PlaceholderText: "#98A2B3",
        QPalette.ColorRole.Highlight: ACCENT,
        QPalette.ColorRole.HighlightedText: SURFACE,
        QPalette.ColorRole.Mid: BORDER,
        QPalette.ColorRole.Midlight: "#F2F4F7",
    }
    for role, colour in roles.items():
        palette.setColor(role, QColor(colour))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)


def set_role(widget, role: str) -> None:
    """Apply a button role defined in the stylesheet (primary, ghost, stepper, chip)."""
    widget.setProperty("role", role)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
