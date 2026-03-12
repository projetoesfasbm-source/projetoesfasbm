# backend/services/xlsx_service.py

from __future__ import annotations
from io import BytesIO
from typing import Any, Iterable, Optional
from datetime import date
import locale

# Importações de openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins
from openpyxl.utils.cell import range_boundaries

# Configuração de locale para garantir o nome do mês em português
try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil') # Windows
    except locale.Error:
        print("Aviso: Não foi possível definir o locale para pt_BR.")

__all__ = ["gerar_mapa_gratificacao_xlsx"]

# --- Helpers ---
def _safe(obj: Any, path: str, default: Any = None) -> Any:
    """Navega de forma segura em dicionários ou objetos"""
    cur = obj
    for part in path.split("."):
        if cur is None: return default
        if isinstance(cur, dict): cur = cur.get(part)
        else: cur = getattr(cur, part, None)
    return default if cur is None else cur

def _iter_disciplinas(instrutor: Any):
    if isinstance(instrutor, dict): return instrutor.get("disciplinas") or []
    return getattr(instrutor, "disciplinas", []) or []

def _apply_border_to_range(ws, cell_range_string, border_style):
    min_col, min_row, max_col, max_row = range_boundaries(cell_range_string)
    for row in ws.iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col):
        for cell in row:
            cell.border = border_style

# --- Função Principal Atualizada ---
def gerar_mapa_gratificacao_xlsx(
    dados: Iterable[Any], valor_hora_aula: float, nome_mes_ano: str, titulo_curso: str,
    opm_nome: str, escola_nome: str, data_emissao: Optional[date],
    telefone: Optional[str] = None, auxiliar_nome: Optional[str] = None,
    comandante_nome: Optional[str] = None, digitador_nome: Optional[str] = None,
    auxiliar_funcao: Optional[str] = None, comandante_funcao: Optional[str] = None,
    *, data_fim: Optional[date] = None, cidade_assinatura: Optional[str] = "Santa Maria",
) -> bytes:
    valor_hora_aula = float(valor_hora_aula or 0)
    wb = Workbook()
    ws = wb.active
    ws.title = "Mapa de Horas"

    # 1. Configurações de Página e Colunas
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_margins = PageMargins(left=0.5, right=0.5, top=0.5, bottom=0.5)
    ws.sheet_view.showGridLines = False
    
    ws.column_dimensions['A'].width = 18 # Posto
    ws.column_dimensions['B'].width = 12 # Id Func
    ws.column_dimensions['C'].width = 35 # Nome
    ws.column_dimensions['D'].width = 30 # Disciplina
    ws.column_dimensions['E'].width = 10 # CH Total
    ws.column_dimensions['F'].width = 15 # CH Anterior
    ws.column_dimensions['G'].width = 10 # CH Pagar
    ws.column_dimensions['H'].width = 15 # Valor R$

    # 2. Definição de Estilos
    thin_border_side = Side(style="thin", color="000000")
    border_all = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
    
    center_align_wrap = Alignment(horizontal="center", vertical="center", wrap_text=True)
    center_top_align_wrap = Alignment(horizontal="center", vertical="top", wrap_text=True)
    left_align_wrap = Alignment(horizontal="left", vertical="center", wrap_text=True)
    right_align_wrap = Alignment(horizontal="right", vertical="center", wrap_text=True)
    left_top_align_wrap = Alignment(horizontal="left", vertical="top", wrap_text=True)

    header_font = Font(name='Times New Roman', size=11)
    table_header_font = Font(name='Calibri', bold=True, size=11)
    table_data_font = Font(name='Calibri', size=11)
    total_font = Font(name='Calibri', bold=True, size=11)
    signature_font = Font(name='Times New Roman', size=11)

    # 3. Construção do Cabeçalho
    ws.merge_cells("A1:B8")
    ws.cell(1, 1).value = f"\n\n\n\n\n________________________\n{comandante_nome or 'Nome Comandante'}\n{comandante_funcao or 'Comandante da EsFAS'}"
    ws.cell(1, 1).font = Font(name='Times New Roman', bold=True, size=10)
    ws.cell(1, 1).alignment = center_top_align_wrap
    _apply_border_to_range(ws, "A1:B8", border_all)

    ws.merge_cells("C1:D5")
    header_text = f"MAPA DE GRATIFICAÇÃO MAGISTÉRIO\nOPM: {opm_nome}\nTelefone: {telefone or 'N/D'}\nHoras aulas a pagar do Mês de {nome_mes_ano}\n{titulo_curso}"
    ws.cell(1, 3).value = header_text
    ws.cell(1, 3).font = header_font
    ws.cell(1, 3).alignment = center_align_wrap

    ws.merge_cells("E1:H8")
    rhe_text = "LANÇAR NO RHE\n____/_____/_____\n\n\n\n\n____________________\nCh da SEÇÃO ADM DE"
    ws.cell(1, 5).value = rhe_text
    ws.cell(1, 5).font = Font(name='Times New Roman', bold=True, size=11)
    ws.cell(1, 5).alignment = center_top_align_wrap
    _apply_border_to_range(ws, "E1:H8", border_all)
    
    current_row = 9

    # 4. Cabeçalho da Tabela
    headers = ["Posto / graduação", "Id. Func.", "Nome completo do servidor", "Disciplina", "CH total", "CH paga anteriormente", "CH a pagar", "Valor em R$"]
    for col_idx, text in enumerate(headers, 1):
        cell = ws.cell(current_row, col_idx, text)
        cell.font = table_header_font
        cell.alignment = center_align_wrap
        cell.border = border_all
    current_row += 1

    # 5. Dados da Tabela
    total_ch_a_pagar_sum = 0.0
    total_valor_sum = 0.0
    
    if dados:
        # Ordenação por ID Funcional (Matrícula)
        for instrutor in sorted(dados, key=lambda i: str(_safe(i, "matricula", ""))):
            for disc in _iter_disciplinas(instrutor):
                ws.row_dimensions[current_row].height = 25
                
                # Coleta valores (podem vir da edição manual)
                ch_total = float(_safe(disc, "ch_total_disciplina", 0))
                ch_anterior = float(_safe(disc, "ch_anterior", 0))
                ch_mes = float(_safe(disc, "ch_mes", 0))
                valor_a_pagar = ch_mes * valor_hora_aula

                row_data = [
                    _safe(instrutor, "posto", "N/D"),
                    _safe(instrutor, "matricula", ""),
                    _safe(instrutor, "nome", ""),
                    _safe(disc, "nome_disciplina", ""),
                    ch_total,
                    ch_anterior,
                    ch_mes, # CH a pagar este mês
                    valor_a_pagar
                ]

                for col_idx, value in enumerate(row_data, 1):
                    cell = ws.cell(row=current_row, column=col_idx, value=value)
                    cell.font = table_data_font
                    cell.border = border_all
                    if col_idx in [1, 2, 5, 6, 7]: cell.alignment = center_align_wrap
                    else: cell.alignment = left_align_wrap
                    
                    if col_idx == 8: cell.number_format = 'R$ #,##0.00'
                    elif col_idx in [5, 6, 7]: cell.number_format = '0.0'

                total_ch_a_pagar_sum += ch_mes
                total_valor_sum += valor_a_pagar
                current_row += 1
    else:
        ws.merge_cells(f"A{current_row}:H{current_row}")
        cell = ws.cell(current_row, 1, "Nenhum dado encontrado.")
        cell.alignment = center_align_wrap; cell.border = border_all
        current_row += 1

    # 6. Linha de Totais
    ws.merge_cells(f"A{current_row}:F{current_row}")
    cell = ws.cell(current_row, 1, "CARGA HORARIA TOTAL")
    cell.font = total_font; cell.alignment = right_align_wrap; cell.border = border_all
    
    ws.cell(current_row, 7, total_ch_a_pagar_sum).font = total_font
    ws.cell(current_row, 7).alignment = center_align_wrap; ws.cell(current_row, 7).border = border_all
    
    ws.cell(current_row, 8, total_valor_sum).font = total_font
    ws.cell(current_row, 8).alignment = right_align_wrap; ws.cell(current_row, 8).border = border_all; ws.cell(current_row, 8).number_format = 'R$ #,##0.00'
    current_row += 2

    # 7. Rodapé de Assinaturas
    bottom_block_start_row = current_row
    ws.merge_cells(f"A{bottom_block_start_row}:F{bottom_block_start_row + 8}")
    orientacoes_text = "ORIENTAÇÕES:\n1. Id. Func. em ordem crescente.\n2. Mapa deverá dar entrada no DE até o dia 05 de cada mês."
    cell = ws.cell(bottom_block_start_row, 1, orientacoes_text)
    cell.alignment = left_top_align_wrap; cell.border = border_all
    _apply_border_to_range(ws, f"A{bottom_block_start_row}:F{bottom_block_start_row + 8}", border_all)

    ws.merge_cells(f"G{bottom_block_start_row}:H{bottom_block_start_row + 8}")
    data_str = data_fim.strftime('%d de %B de %Y') if data_fim else "____/____/____"
    assinaturas_text = f"Quartel em {cidade_assinatura}, {data_str}.\n\n\n____________________\n{auxiliar_nome or 'Auxiliar'}\nDigitador: {digitador_nome or ''}"
    cell = ws.cell(bottom_block_start_row, 7, assinaturas_text)
    cell.alignment = center_top_align_wrap; cell.border = border_all
    _apply_border_to_range(ws, f"G{bottom_block_start_row}:H{bottom_block_start_row + 8}", border_all)

    # 8. Exportação
    out = BytesIO()
    wb.save(out)
    return out.getvalue()