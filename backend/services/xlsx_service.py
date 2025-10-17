# backend/services/xlsx_service.py
from __future__ import annotations
from io import BytesIO
from typing import List, Sequence, Optional

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter

# Texto do rodapé — fiel ao modelo enviado
FOOTER_LINES: List[str] = [
    "1.     Id. Func. em ordem crescente.",
    "2.     Mapa deverá dar entrada no DE até o dia 05 de cada mês.",
    "3.     Mapa atrasado do mês anterior ficará para o próximo mês, cumulativamente como do mês vigente.",
    "4.     Mapas atrasados com mais de dois meses deverão ser devidamente fundamentados pelo comandante da escola, sob penada não aceitação e restituição.",
    "5.     Nos termos do item anterior, após chegar fundamentado, será adotada a medida da letra “g”, nº 5 do Item nº 3",
]

THIN = Side(style="thin", color="000000")
BORDER_THIN = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

HEADER_FILL = PatternFill("solid", fgColor="F2F2F2")

def _set_col_widths(ws: Worksheet, widths: Sequence[float]) -> None:
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width

def _add_title(ws: Worksheet, title: str, cols: int) -> None:
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=cols)
    cell = ws.cell(row=1, column=1, value=title)
    cell.font = Font(bold=True, size=14)
    cell.alignment = Alignment(horizontal="center", vertical="center")

def _add_headers(ws: Worksheet, headers: Sequence[str], start_row: int = 3) -> int:
    for col, h in enumerate(headers, start=1):
        c = ws.cell(row=start_row, column=col, value=h)
        c.font = Font(bold=True, size=11)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER_THIN
        c.fill = HEADER_FILL
    return start_row + 1

def _add_rows(ws: Worksheet, rows: Sequence[Sequence[object]], start_row: int) -> int:
    r = start_row
    for row in rows:
        for col, val in enumerate(row, start=1):
            c = ws.cell(row=r, column=col, value=val)
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            c.border = BORDER_THIN
        r += 1
    return r

def _add_separator_line(ws: Worksheet, row: int, cols: int) -> None:
    # Linha visual antes do rodapé
    for col in range(1, cols + 1):
        c = ws.cell(row=row, column=col, value=None)
        c.border = Border(bottom=THIN)

def _add_footer(ws: Worksheet, start_row: int, cols: int) -> int:
    """
    Adiciona o bloco de observações exatamente como no modelo.
    - Uma linha divisória acima
    - Texto com quebra de linha, alinhado à esquerda, fonte menor
    """
    _add_separator_line(ws, start_row, cols)
    start_row += 1

    text = "\n".join(FOOTER_LINES)

    ws.merge_cells(start_row=start_row, start_column=1, end_row=start_row + 5, end_column=cols)
    c = ws.cell(row=start_row, column=1, value=text)
    c.font = Font(size=9)  # fonte menor
    c.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)

    # Borda em volta do bloco inteiro para “fechar” visualmente as observações
    for r in range(start_row, start_row + 6):
        for col in range(1, cols + 1):
            ws.cell(row=r, column=col).border = BORDER_THIN

    return start_row + 6

def _setup_print(ws: Worksheet) -> None:
    # Página: margens e ajuste para caber na largura
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True

    # Margens agradáveis para impressão
    ws.page_margins.left = 0.4
    ws.page_margins.right = 0.4
    ws.page_margins.top = 0.6
    ws.page_margins.bottom = 0.6

def make_xlsx(
    headers: Sequence[str],
    rows: Sequence[Sequence[object]],
    *,
    title: str = "MAPA DE GRATIFICAÇÃO MAGISTÉRIO",
    column_widths: Optional[Sequence[float]] = None,
) -> bytes:
    """
    Cria um XLSX com cabeçalho, tabela e rodapé de observações.
    - headers: títulos das colunas
    - rows: dados (lista de linhas)
    - title: título centralizado
    - column_widths: larguras opcionais; se None, aplica um padrão
    Retorna bytes do arquivo XLSX.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Relatório"

    cols = len(headers)
    if not column_widths:
        # Sugestão de largura padrão (ajuste conforme seu layout)
        column_widths = [12] + [18] * (cols - 1)
    _set_col_widths(ws, column_widths)

    _add_title(ws, title, cols)
    data_start = _add_headers(ws, headers, start_row=3)
    data_end = _add_rows(ws, rows, data_start)

    # Altura padrão das linhas (facilita leitura)
    for r in range(3, data_end):
        ws.row_dimensions[r].height = 20

    footer_start_row = data_end + 1
    end_row = _add_footer(ws, footer_start_row, cols)

    _setup_print(ws)

    # Congelar painéis (cabeçalho sempre visível)
    ws.freeze_panes = ws["A4"]

    # Salvar
    buff = BytesIO()
    wb.save(buff)
    return buff.getvalue()


# --- Compatibilidade retroativa ---
def gerar_mapa_gratificacao_xlsx(headers, rows, **kwargs) -> bytes:
    """Alias para manter compatibilidade com código legado."""
    return make_xlsx(headers, rows, **kwargs)
