"""Entry point: python -m zkreport"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt6.QtCore import QLibraryInfo, QLocale, QStandardPaths, QTranslator
from PyQt6.QtWidgets import QApplication

from zkreport.store.settings_store import SettingsStore
from zkreport.ui.main_window import MainWindow


def settings_path() -> Path:
    override = os.environ.get("ZKREPORT_SETTINGS")
    if override:
        return Path(override)
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(base) / "settings.db"


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName("ZKReport")
    app.setApplicationName("ZKReport")
    QLocale.setDefault(QLocale(QLocale.Language.French, QLocale.Country.Tunisia))
    translator = QTranslator(app)
    if translator.load("qtbase_fr", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)

    store = SettingsStore(settings_path())
    window = MainWindow(store)
    window.show()
    window.refresh()
    code = app.exec()
    store.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
