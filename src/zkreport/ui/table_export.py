"""Excel / PDF / print buttons for a table. The page supplies a TableExport snapshot."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QMarginsF, QStandardPaths, Qt, pyqtSignal
from PyQt6.QtGui import QPageLayout, QPageSize, QTextDocument
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QMessageBox, QPushButton, QWidget

from zkreport.export import TableExport, build_html, export_xlsx

from .table_models import NUMERIC, ResultsFilterProxy, display, row_fill


def snapshot(proxy: ResultsFilterProxy, title: str, meta: list[str]) -> TableExport:
    """Visible rows in on-screen order, with on-screen text and row colours."""
    columns = proxy.sourceModel().columns
    rows = proxy.visible_rows()
    return TableExport(
        title=title,
        meta=tuple(meta),
        headers=tuple(proxy.sourceModel().headerData(i, Qt.Orientation.Horizontal)
                      for i in range(len(columns))),
        rows=tuple(tuple(display(r, key) for key in columns) for r in rows),
        row_fills=tuple(row_fill(r) for r in rows),
        numeric_columns=frozenset(i for i, key in enumerate(columns) if key in NUMERIC),
    )


def _document(table: TableExport) -> QTextDocument:
    doc = QTextDocument()
    doc.setHtml(build_html(table))
    return doc


def _setup(printer: QPrinter) -> None:
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageOrientation(QPageLayout.Orientation.Portrait)
    printer.setPageMargins(QMarginsF(12, 12, 12, 12), QPageLayout.Unit.Millimeter)


def write_pdf(table: TableExport, path: str | Path) -> None:
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(path))
    printer.setDocName(table.title)
    _setup(printer)
    _document(table).print(printer)


class ExportBar(QWidget):
    """Three buttons. `provider()` returns (TableExport, base file name) or None."""

    message = pyqtSignal(str)

    def __init__(self, provider: Callable[[], tuple[TableExport, str] | None], parent=None):
        super().__init__(parent)
        self._provider = provider
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.excel_button = QPushButton("Exporter Excel")
        self.pdf_button = QPushButton("Exporter PDF")
        self.print_button = QPushButton("Imprimer")
        self.excel_button.clicked.connect(self.export_excel)
        self.pdf_button.clicked.connect(self.export_pdf)
        self.print_button.clicked.connect(self.print_table)
        for button in (self.excel_button, self.pdf_button, self.print_button):
            layout.addWidget(button)

    def set_enabled(self, enabled: bool) -> None:
        for button in (self.excel_button, self.pdf_button, self.print_button):
            button.setEnabled(enabled)

    def _ask_path(self, base: str, caption: str, suffix: str, filter_text: str) -> str | None:
        folder = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        path, _ = QFileDialog.getSaveFileName(self, caption, str(Path(folder) / f"{base}{suffix}"),
                                              filter_text)
        if not path:
            return None
        return path if path.lower().endswith(suffix) else path + suffix

    def _get(self):
        data = self._provider()
        if data is None:
            QMessageBox.information(self, "Export", "Aucune donnée à exporter.")
        return data

    def export_excel(self) -> None:
        data = self._get()
        if not data:
            return
        table, base = data
        path = self._ask_path(base, "Exporter en Excel", ".xlsx", "Classeur Excel (*.xlsx)")
        if path:
            self._run(lambda: export_xlsx(table, path), path)

    def export_pdf(self) -> None:
        data = self._get()
        if not data:
            return
        table, base = data
        path = self._ask_path(base, "Exporter en PDF", ".pdf", "Document PDF (*.pdf)")
        if path:
            self._run(lambda: write_pdf(table, path), path)

    def print_table(self) -> None:
        data = self._get()
        if not data:
            return
        table, _ = data
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        _setup(printer)
        printer.setDocName(table.title)
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Imprimer")
        if dialog.exec():
            _document(table).print(printer)
            self.message.emit("Document envoyé à l'imprimante.")

    def _run(self, action: Callable[[], None], path: str) -> None:
        try:
            action()
        except OSError as exc:
            QMessageBox.warning(self, "Export", f"Impossible d'écrire le fichier :\n{exc}")
            return
        self.message.emit(f"Exporté : {path}")
