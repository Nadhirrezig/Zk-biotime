"""Table export to Excel and to HTML (used for PDF and printing). No Qt here."""
from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


@dataclass(frozen=True)
class TableExport:
    title: str
    meta: tuple[str, ...]                 # e.g. filters, counts
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    row_fills: tuple[str | None, ...] = field(default=())  # "#RRGGBB" per row or None
    numeric_columns: frozenset[int] = frozenset()          # written as numbers in Excel

    def fill(self, index: int) -> str | None:
        return self.row_fills[index] if index < len(self.row_fills) else None


def export_xlsx(table: TableExport, path: str | Path, sheet_name: str = "Présence") -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name[:31]
    ws.append([table.title])
    ws["A1"].font = Font(bold=True, size=14)
    for line in table.meta:
        ws.append([line])
    ws.append([])
    ws.append(list(table.headers))
    header_row = ws.max_row  # read after writing: append([]) does not raise max_row
    thin = Side(style="thin", color="D0D5DD")
    for cell in ws[header_row]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="F2F4F7")
        cell.border = Border(bottom=thin)
        cell.alignment = Alignment(vertical="center")
    for i, row in enumerate(table.rows):
        ws.append([int(v) if c in table.numeric_columns and v.isdigit() else v
                   for c, v in enumerate(row)])
        colour = table.fill(i)
        if colour:
            for cell in ws[ws.max_row]:
                cell.fill = PatternFill("solid", fgColor=colour.lstrip("#").upper())
    for col, header in enumerate(table.headers, start=1):
        width = max([len(header)] + [len(r[col - 1]) for r in table.rows if col - 1 < len(r)])
        ws.column_dimensions[get_column_letter(col)].width = min(max(width + 2, 8), 60)
    last_col = get_column_letter(len(table.headers))
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    ws.auto_filter.ref = f"A{header_row}:{last_col}{max(ws.max_row, header_row)}"
    ws.page_setup.orientation = "landscape" if len(table.headers) > 7 else "portrait"
    ws.page_setup.fitToWidth = 1
    ws.print_title_rows = f"{header_row}:{header_row}"
    wb.save(str(path))


def build_html(table: TableExport) -> str:
    """Self-contained HTML for QTextDocument (PDF export and printing)."""
    head = "".join(f"<th>{escape(h)}</th>" for h in table.headers)
    body = []
    for i, row in enumerate(table.rows):
        colour = table.fill(i)
        style = f" style='background-color:{colour}'" if colour else ""
        cells = "".join(f"<td>{escape(v)}</td>" for v in row)
        body.append(f"<tr{style}>{cells}</tr>")
    meta = "".join(f"<p class='meta'>{escape(line)}</p>" for line in table.meta)
    return (
        "<html><head><meta charset='utf-8'><style>"
        "body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 9pt; color: #101828; }"
        "h1 { font-size: 15pt; margin: 0 0 4px 0; }"
        ".meta { color: #475467; margin: 0 0 2px 0; }"
        "table { border-collapse: collapse; margin-top: 8px; }"
        "th { background-color: #F2F4F7; text-align: left; font-weight: 600; }"
        "th, td { border: 1px solid #D0D5DD; padding: 3px 6px; }"
        "</style></head><body>"
        f"<h1>{escape(table.title)}</h1>{meta}"
        f"<table width='100%' cellspacing='0'><thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table>"
        "</body></html>"
    )
