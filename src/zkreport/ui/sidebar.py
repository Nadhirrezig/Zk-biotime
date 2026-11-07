"""Dark sidebar: app name, page navigation, settings, refresh and data status."""
from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QButtonGroup, QFrame, QLabel, QPushButton, QVBoxLayout

from . import theme as t
from .icons import icon

NAV_STYLE = f"""
QPushButton {{
    background: transparent; color: {t.SIDEBAR_TEXT}; border: none; border-radius: 8px;
    padding: 9px 12px; text-align: left; font-weight: 600; font-size: 13px;
}}
QPushButton:hover {{ background: {t.SIDEBAR_HOVER}; color: {t.SIDEBAR_TEXT_ACTIVE}; }}
QPushButton:checked {{ background: {t.SIDEBAR_ACTIVE}; color: {t.SIDEBAR_TEXT_ACTIVE}; }}
QPushButton:focus {{ outline: none; }}
"""


class Sidebar(QFrame):
    page_requested = pyqtSignal(int)
    settings_requested = pyqtSignal()
    refresh_requested = pyqtSignal()

    def __init__(self, pages: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(228)
        self.setStyleSheet(f"#sidebar {{ background: {t.SIDEBAR_BG}; }}"
                           f"#sidebar QLabel {{ background: transparent; }}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 18, 14, 16)
        layout.setSpacing(4)

        brand = QLabel("ZK <span style='color:#8098F9'>Présence</span>")
        brand.setTextFormat(Qt.TextFormat.RichText)
        brand.setStyleSheet("color: white; font-size: 18px; font-weight: 800;")
        badge = QLabel("LECTURE SEULE")
        badge.setStyleSheet(f"color: {t.SIDEBAR_MUTED}; font-size: 10px; font-weight: 700;"
                            " letter-spacing: 1px;")
        layout.addWidget(brand)
        layout.addWidget(badge)
        layout.addSpacing(22)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: list[QPushButton] = []
        for index, (label, kind) in enumerate(pages):
            button = self._nav_button(label, kind)
            button.setCheckable(True)
            self.group.addButton(button, index)
            layout.addWidget(button)
            self.buttons.append(button)
        self.buttons[0].setChecked(True)
        self.group.idClicked.connect(self.page_requested)

        layout.addStretch(1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color: {t.SIDEBAR_TEXT}; font-size: 11px; line-height: 140%;")
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: #A6F4C5; font-size: 11px;")
        self.message.hide()
        refresh = self._nav_button("Actualiser", "refresh")
        refresh.setToolTip("Recharger les données (F5)")
        refresh.clicked.connect(self.refresh_requested)
        settings = self._nav_button("Paramètres", "settings")
        settings.clicked.connect(self.settings_requested)
        layout.addWidget(self.status)
        layout.addWidget(self.message)
        layout.addSpacing(8)
        layout.addWidget(refresh)
        layout.addWidget(settings)

    def _nav_button(self, label: str, kind: str) -> QPushButton:
        button = QPushButton(label)
        button.setIcon(icon(kind, "#C9D2E3"))
        button.setIconSize(QSize(18, 18))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(NAV_STYLE)
        return button

    def set_current(self, index: int) -> None:
        self.buttons[index].setChecked(True)
