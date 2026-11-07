"""Light theme tokens shared by the dashboard and the tables."""
from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

# Neutrals
PAGE_BG = "#F4F5F7"
SURFACE = "#FFFFFF"
BORDER = "#E4E7EC"
BORDER_HOVER = "#C5CBD3"
TEXT = "#101828"
TEXT_MUTED = "#667085"
TRACK = "#EAECF0"
FOCUS = "#84ADFF"


@dataclass(frozen=True)
class Tone:
    """One semantic colour: `solid` for bars/icons, `text` for numbers (WCAG AA on white
    and on `tint`), `tint` for icon/selected backgrounds."""
    solid: str
    text: str
    tint: str


PRESENT = Tone("#16A34A", "#15803D", "#ECFDF3")
COMPLETE = Tone("#2563EB", "#1D4ED8", "#EFF4FF")
SINGLE = Tone("#F59E0B", "#B45309", "#FEF6E7")
LATE = Tone("#DC2626", "#B42318", "#FEF3F2")
ABSENT = Tone("#E11D48", "#BE123C", "#FFF1F3")
OTHER = Tone("#98A2B3", "#475467", "#F2F4F7")
NEUTRAL = Tone("#98A2B3", "#344054", "#F2F4F7")

# Table row highlights (same hues as the dashboard)
ROW_SINGLE = "#FDEFC8"
ROW_ABSENT = "#FDE2E7"


def apply_light_theme(app: QApplication) -> None:
    """Fusion style with a fixed light palette, whatever the Windows colour scheme."""
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
        QPalette.ColorRole.PlaceholderText: TEXT_MUTED,
        QPalette.ColorRole.Highlight: "#D1E0FF",
        QPalette.ColorRole.HighlightedText: TEXT,
        QPalette.ColorRole.Mid: BORDER,
        QPalette.ColorRole.Midlight: "#F2F4F7",
    }
    for role, colour in roles.items():
        palette.setColor(role, QColor(colour))
    app.setPalette(palette)
