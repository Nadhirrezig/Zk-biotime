"""Excel and HTML export (no Qt)."""
from openpyxl import load_workbook

from zkreport.export import TableExport, build_html, export_xlsx

TABLE = TableExport(
    title="Présence du jeudi 24 septembre 2026",
    meta=("Pointage double : 2", "Filtre : Pointage unique"),
    headers=("Matricule", "Nom", "Pointages", "Statut"),
    rows=(("302", "Rahma <Achour>", "1", "Pointage unique (arrivée manquante)"),
          ("247", "Hassen", "2", "Pointage double")),
    row_fills=("#FDEFC8", None),
    numeric_columns=frozenset({2}),
)


def test_xlsx_layout(tmp_path):
    path = tmp_path / "t.xlsx"
    export_xlsx(TABLE, path)
    ws = load_workbook(path).active
    assert ws["A1"].value == TABLE.title
    assert [ws["A2"].value, ws["A3"].value] == list(TABLE.meta)
    header_row = 5
    assert [c.value for c in ws[header_row]] == list(TABLE.headers)
    assert [c.value for c in ws[header_row + 1]] == ["302", "Rahma <Achour>", 1,
                                                     "Pointage unique (arrivée manquante)"]
    assert ws.cell(header_row + 1, 1).fill.fgColor.rgb.endswith("FDEFC8")
    assert ws.freeze_panes == f"A{header_row + 1}"
    assert ws.auto_filter.ref == f"A{header_row}:D{header_row + 2}"


def test_html_escapes_and_colours():
    html = build_html(TABLE)
    assert "Rahma &lt;Achour&gt;" in html
    assert "background-color:#FDEFC8" in html
    assert html.count("<tr") == 3


def test_xlsx_header_is_styled(tmp_path):
    path = tmp_path / "t.xlsx"
    export_xlsx(TABLE, path)
    ws = load_workbook(path).active
    assert ws.cell(5, 1).font.bold
    assert ws.cell(4, 1).value is None
