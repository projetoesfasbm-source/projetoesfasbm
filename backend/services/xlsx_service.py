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

# --- Função Principal Definitiva ---
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
    
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 12
    ws.column_dimensions['C'].width = 35
    ws.column_dimensions['D'].width = 35
    ws.column_dimensions['E'].width = 9
    ws.column_dimensions['F'].width = 14
    ws.column_dimensions['G'].width = 9
    ws.column_dimensions['H'].width = 15

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
    for i in range(1, 9): ws.row_dimensions[i].height = 15
    ws.row_dimensions[5].height = 18

    ws.merge_cells("A1:B8")
    ws.cell(1, 1).value = f"\n\n\n\n\n________________________\n{comandante_nome or 'Nome Comandante'}\n{comandante_funcao or 'Comandante da EsFAS'}"
    ws.cell(1, 1).font = Font(name='Times New Roman', bold=True, size=11)
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
    ws.row_dimensions[current_row].height = 20
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
        # --- ALTERAÇÃO AQUI: ORDENAÇÃO PELA MATRÍCULA (ID. FUNC.) ---
        # Antes ordenava por "info.user.nome_completo", agora por "info.user.matricula"
        for instrutor in sorted(dados, key=lambda i: _safe(i, "info.user.matricula", "")):
            user = _safe(instrutor, "info.user", {})
            for disc in sorted(_iter_disciplinas(instrutor), key=lambda d: d.get("nome", "")):
                ws.row_dimensions[current_row].height = 30
                ch_a_pagar_val = float(_safe(disc, "ch_a_pagar", 0) or 0)
                valor_a_pagar = ch_a_pagar_val * valor_hora_aula
                row_data = [
                    _safe(user, "posto_graduacao", "N/D"), _safe(user, "matricula", ""),
                    _safe(user, "nome_completo", ""), _safe(disc, "nome", ""),
                    float(_safe(disc, "ch_total", 0) or 0), float(_safe(disc, "ch_paga_anteriormente", 0) or 0),
                    ch_a_pagar_val, valor_a_pagar
                ]
                for col_idx, value in enumerate(row_data, 1):
                    cell = ws.cell(row=current_row, column=col_idx, value=value)
                    cell.font = table_data_font
                    cell.border = border_all
                    if col_idx in [1, 2, 5, 6, 7]: cell.alignment = center_align_wrap
                    else: cell.alignment = left_align_wrap
                    if col_idx == 7: cell.number_format = '0.0'
                    if col_idx == 8: cell.number_format = 'R$ #,##0.00'
                total_ch_a_pagar_sum += ch_a_pagar_val
                total_valor_sum += valor_a_pagar
                current_row += 1
    else:
        ws.merge_cells(f"A{current_row}:H{current_row}")
        cell = ws.cell(current_row, 1, "Nenhum dado encontrado.")
        cell.font = table_data_font; cell.alignment = center_align_wrap; cell.border = border_all
        current_row += 1

    # 6. Linha de Totais
    ws.row_dimensions[current_row].height = 18
    ws.merge_cells(f"A{current_row}:F{current_row}")
    cell = ws.cell(current_row, 1, "CARGA HORARIA TOTAL")
    cell.font = total_font; cell.alignment = right_align_wrap; cell.border = border_all
    _apply_border_to_range(ws, f"A{current_row}:F{current_row}", border_all)
    ws.cell(current_row, 7, total_ch_a_pagar_sum).font = total_font; ws.cell(current_row, 7).alignment = center_align_wrap; ws.cell(current_row, 7).border = border_all; ws.cell(current_row, 7).number_format = '0.0'
    ws.cell(current_row, 8, total_valor_sum).font = total_font; ws.cell(current_row, 8).alignment = right_align_wrap; ws.cell(current_row, 8).border = border_all; ws.cell(current_row, 8).number_format = 'R$ #,##0.00'
    current_row += 2

    # 7. Blocos Inferiores
    bottom_block_start_row = current_row
    for i in range(bottom_block_start_row, bottom_block_start_row + 11): ws.row_dimensions[i].height = 15
    ws.merge_cells(f"A{bottom_block_start_row}:F{bottom_block_start_row + 10}")
    orientacoes_text = ("ORIENTAÇÕES:\n\n" + "\n".join([
        "1. Id. Func. em ordem crescente.", "2. Mapa deverá dar entrada no DE até o dia 05 de cada mês.",
        "3. Mapa atrasado do mês anterior ficará para o próximo mês, cumulativamente como do mês vigente.",
        "4. Mapas atrasados com mais de dois meses deverão ser devidamente fundamentados pelo comandante da escola, sob pena da não aceitação e restituição.",
        "5. Nos termos do item anterior, após chegar fundamentado, será adotada a medida da letra “g”, nº 5 do Item nº 3."]))
    cell = ws.cell(bottom_block_start_row, 1, orientacoes_text)
    cell.font = signature_font; cell.alignment = left_top_align_wrap
    _apply_border_to_range(ws, f"A{bottom_block_start_row}:F{bottom_block_start_row + 10}", border_all)
    
    ws.merge_cells(f"G{bottom_block_start_row}:H{bottom_block_start_row + 10}")
    data_assinatura_str = data_fim.strftime('%d de %B de %Y') if data_fim else "____ de __________ de ____"
    assinaturas_direita_text = f"Quartel em {cidade_assinatura}, {data_assinatura_str}.\n\n\n\n" \
                               f"____________________\n" \
                               f"{auxiliar_nome or ''}\n" \
                               f"{auxiliar_funcao or 'Auxiliar da Seção de Ensino'}" \
                               f"\n\n\n" \
                               f"Em ___/___/___\n" \
                               f"____________\n" \
                               f"Digitador"
    cell = ws.cell(bottom_block_start_row, 7, assinaturas_direita_text)
    cell.font = signature_font; cell.alignment = center_top_align_wrap
    _apply_border_to_range(ws, f"G{bottom_block_start_row}:H{bottom_block_start_row + 10}", border_all)

    # 8. Finalização
    out = BytesIO()
    wb.save(out)
    return out.getvalue()