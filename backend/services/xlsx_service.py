# backend/services/xlsx_service.py

from __future__ import annotations
from io import BytesIO
from typing import Any, Iterable
from typing import Optional
from datetime import date
from textwrap import dedent
import locale
import openpyxl # Importar no topo

# Importações de openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side, NamedStyle
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins
from openpyxl.worksheet.dimensions import RowDimension
from openpyxl.utils.cell import range_boundaries # Para helper de borda

# Configuração de locale (mantida)
try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil') # Windows
    except locale.Error:
        try:
           locale.setlocale(locale.LC_TIME, '') # Usa o padrão do sistema
        except locale.Error:
           print("Aviso: Não foi possível definir o locale para pt_BR ou padrão do sistema.")


__all__ = ["gerar_mapa_gratificacao_xlsx"]


# -------------------------
# Helpers (mantidos)
# -------------------------
def _safe(obj: Any, path: str, default: Any = None) -> Any:
    cur = obj
    for part in path.split("."):
        if cur is None: return default
        if isinstance(cur, dict): cur = cur.get(part, default)
        else: cur = getattr(cur, part, default)
    return default if cur is None else cur

def _iter_disciplinas(instrutor: Any):
    if isinstance(instrutor, dict): return instrutor.get("disciplinas") or []
    return getattr(instrutor, "disciplinas", []) or []

# Helper para aplicar borda a um range de células (REVISADO)
def _apply_border_to_range(ws, cell_range_string, border_style):
    min_col, min_row, max_col, max_row = range_boundaries(cell_range_string)
    for row_idx in range(min_row, max_row + 1):
        for col_idx in range(min_col, max_col + 1):
            # Aplica a borda a cada célula individualmente dentro do range
            ws.cell(row=row_idx, column=col_idx).border = border_style

# Helper para definir valor e estilo na célula superior esquerda de um range mesclado (mantido)
def _style_merged_cell(ws, row, col, value, font=None, alignment=None, fill=None, border=None, number_format=None, style_name=None):
    cell = ws.cell(row=row, column=col, value=value)
    if font: cell.font = font
    if alignment: cell.alignment = alignment
    if fill: cell.fill = fill
    # A borda principal pode ser definida aqui, mas _apply_border_to_range cuidará do range todo
    if border: cell.border = border
    if number_format: cell.number_format = number_format
    if style_name: cell.style = style_name
    return cell

# -------------------------
# Função principal (REVISADA v5 - Foco nas Bordas e Remoção de Assinaturas Extras)
# -------------------------
def gerar_mapa_gratificacao_xlsx(
    dados: Iterable[Any],
    valor_hora_aula: float,
    nome_mes_ano: str,
    titulo_curso: str,
    opm_nome: str,
    escola_nome: str,
    data_emissao: Optional[date],
    telefone: Optional[str] = None,
    auxiliar_nome: Optional[str] = None,
    comandante_nome: Optional[str] = None,
    digitador_nome: Optional[str] = None,
    auxiliar_funcao: Optional[str] = None,
    comandante_funcao: Optional[str] = None,
    *,
    data_fim: Optional[date] = None,
    cidade_assinatura: Optional[str] = "Santa Maria",
) -> bytes:
    """
    Gera arquivo .xlsx com layout revisado para alinhar visualmente a tabela central
    e remover assinaturas extras.
    """

    data_emissao = data_emissao or date.today()
    valor_hora_aula = float(valor_hora_aula or 0)

    wb = Workbook()
    ws = wb.active
    ws.title = f"Mapa {nome_mes_ano.split(' ')[0][:3]}_{nome_mes_ano.split(' ')[-1]}"

    # Configurações de página/visual (mantidas)
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_margins = PageMargins(left=0.6, right=0.6, top=0.4, bottom=0.4)
    ws.sheet_view.showGridLines = False

    # Definições de Layout e Colunas (A-N) (mantidas)
    main_table_start_col_letter = 'D'
    main_table_start_col_idx = 4
    main_table_end_col_letter = 'K'
    main_table_end_col_idx = 11

    ws.column_dimensions['A'].width = 12; ws.column_dimensions['B'].width = 12; ws.column_dimensions['C'].width = 12
    ws.column_dimensions['D'].width = 18; ws.column_dimensions['E'].width = 14; ws.column_dimensions['F'].width = 35
    ws.column_dimensions['G'].width = 32; ws.column_dimensions['H'].width = 10; ws.column_dimensions['I'].width = 22
    ws.column_dimensions['J'].width = 12; ws.column_dimensions['K'].width = 18
    ws.column_dimensions['L'].width = 12; ws.column_dimensions['M'].width = 12; ws.column_dimensions['N'].width = 12

    # Estilos (mantidos)
    gray_fill = PatternFill("solid", fgColor="D9D9D9")
    thin_border_side = Side(style="thin", color="000000")
    border_all = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    center_top_align = Alignment(horizontal="center", vertical="top", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
    left_top_align = Alignment(horizontal="left", vertical="top", wrap_text=True)
    right_align = Alignment(horizontal="right", vertical="center", wrap_text=True)

    header_font = Font(name='Times New Roman', size=11)
    header_bold_font = Font(name='Times New Roman', bold=True, size=11)
    main_title_font = Font(name='Times New Roman', bold=True, size=14)
    table_header_font = Font(name='Times New Roman', bold=True, size=10)
    table_data_font = Font(name='Times New Roman', size=10)
    total_font = Font(name='Times New Roman', bold=True, size=10)
    signature_font = Font(name='Times New Roman', size=10)

    # Estilo de moeda (mantido)
    brl_style_name = "BRL"
    if brl_style_name not in wb.named_styles:
        brl_style = NamedStyle(name=brl_style_name, font=table_data_font, alignment=right_align)
        brl_style.number_format = 'R$ #,##0.00;-R$ #,##0.00'
        wb.add_named_style(brl_style)

    # --- BLOCOS SUPERIORES ---
    current_row = 1
    # Bloco Esquerdo (Comandante) - A1:C6
    range_bloco_esq = f"A{current_row}:C{current_row+5}"
    ws.merge_cells(range_bloco_esq)
    assinatura_cmd_txt = f"*\n\n\n____________________________________\n{comandante_nome or 'Nome Comandante'}\n{comandante_funcao or 'Comandante da EsFAS-SM'}"
    _style_merged_cell(ws, current_row, 1, assinatura_cmd_txt, font=signature_font, alignment=center_top_align)
    _apply_border_to_range(ws, range_bloco_esq, border_all) # Aplica borda ao range todo

    # Bloco Direito (RHE) - L1:N6
    range_bloco_dir = f"L{current_row}:N{current_row+5}"
    ws.merge_cells(range_bloco_dir)
    rhe_txt = "LANÇAR NO RHE\n____/_____/_____\n\n\n____________________\nCh da SEÇÃO ADM DE"
    _style_merged_cell(ws, current_row, 12, rhe_txt, font=signature_font, alignment=center_top_align)
    _apply_border_to_range(ws, range_bloco_dir, border_all) # Aplica borda ao range todo

    # Bloco Central (Títulos) - D1:K6
    range_titulo = f"D{current_row}:K{current_row}"
    ws.merge_cells(range_titulo)
    _style_merged_cell(ws, current_row, 4, "MAPA DE GRATIFICAÇÃO MAGISTÉRIO", font=main_title_font, alignment=center_align)
    current_row += 1
    range_opm = f"D{current_row}:K{current_row}"
    ws.merge_cells(range_opm)
    _style_merged_cell(ws, current_row, 4, f"OPM: {opm_nome}", font=header_font, alignment=center_align)
    current_row += 1
    range_tel = f"D{current_row}:K{current_row}"
    ws.merge_cells(range_tel)
    _style_merged_cell(ws, current_row, 4, f"Telefone: {telefone or '(não informado)'}", font=header_font, alignment=center_align)
    current_row += 1
    range_mes = f"D{current_row}:K{current_row}"
    ws.merge_cells(range_mes)
    _style_merged_cell(ws, current_row, 4, f"Horas aulas a pagar do Mês de {nome_mes_ano}", font=header_bold_font, alignment=center_align)
    current_row += 1
    range_curso = f"D{current_row}:K{current_row}"
    ws.merge_cells(range_curso)
    _style_merged_cell(ws, current_row, 4, titulo_curso, font=header_bold_font, alignment=center_align)

    current_row = 7 # Garante que a tabela comece na linha 8
    table_start_row = current_row + 1 # Linha 8

    # --- CABEÇALHO DA TABELA PRINCIPAL --- D8:K8
    headers = [
        "Posto / graduação", "Id. Func.", "Nome completo do servidor", "Disciplina",
        "CH total", "CH paga anteriormente", "CH a pagar", "Valor em R$"
    ]
    for c_offset, text in enumerate(headers):
        col_idx = main_table_start_col_idx + c_offset
        cell = ws.cell(table_start_row, col_idx, text)
        cell.fill = gray_fill
        cell.font = table_header_font
        cell.alignment = center_align
        cell.border = border_all
    current_row = table_start_row + 1 # Próxima linha para dados é a 9

    # --- DADOS DA TABELA PRINCIPAL ---
    total_ch_a_pagar_sum = 0
    total_valor_sum = 0.0
    data_row_start = current_row
    if dados:
        for instrutor in dados:
            user = _safe(instrutor, "info.user", {})
            for disc in _iter_disciplinas(instrutor):
                ch_a_pagar_val = float(_safe(disc, "ch_a_pagar", 0) or 0)
                valor_a_pagar = ch_a_pagar_val * valor_hora_aula
                row_vals = [
                    _safe(user, "posto_graduacao", "N/D"), _safe(user, "matricula", ""),
                    _safe(user, "nome_completo", ""), _safe(disc, "nome", ""),
                    float(_safe(disc, "ch_total", 0) or 0), float(_safe(disc, "ch_paga_anteriormente", 0) or 0),
                    ch_a_pagar_val, round(valor_a_pagar, 2)
                ]
                for c_offset, v in enumerate(row_vals):
                    col_idx = main_table_start_col_idx + c_offset
                    cell = ws.cell(current_row, col_idx, v)
                    cell.border = border_all
                    cell.font = table_data_font
                    if c_offset in [0, 1, 4, 5, 6]: cell.alignment = center_align
                    elif c_offset in [2, 3]: cell.alignment = left_align
                    elif c_offset == 7: cell.style = brl_style_name
                total_ch_a_pagar_sum += ch_a_pagar_val
                total_valor_sum += valor_a_pagar
                current_row += 1
    else:
        # Linha de "Nenhum dado"
        range_nodata = f"{main_table_start_col_letter}{current_row}:{main_table_end_col_letter}{current_row}"
        ws.merge_cells(range_nodata)
        _style_merged_cell(ws, current_row, main_table_start_col_idx, "Nenhum dado encontrado para o período e filtros selecionados.", font=table_data_font, alignment=center_align)
        _apply_border_to_range(ws, range_nodata, border_all) # Borda no range
        current_row += 1

    data_row_end = current_row - 1

    # --- LINHA DE TOTAIS ---
    range_total_label = f"{main_table_start_col_letter}{current_row}:{get_column_letter(main_table_end_col_idx - 2)}{current_row}"
    ws.merge_cells(range_total_label)
    _style_merged_cell(ws, current_row, main_table_start_col_idx, "CARGA HORÁRIA TOTAL",
                       font=total_font, alignment=right_align, fill=gray_fill)
    _style_merged_cell(ws, current_row, main_table_end_col_idx - 1, total_ch_a_pagar_sum,
                       font=total_font, alignment=center_align, fill=gray_fill, number_format='0.0')
    _style_merged_cell(ws, current_row, main_table_end_col_idx, round(total_valor_sum, 2),
                       font=total_font, fill=gray_fill, style_name=brl_style_name)
    _apply_border_to_range(ws, f"{main_table_start_col_letter}{current_row}:{main_table_end_col_letter}{current_row}", border_all) # Borda em toda linha total

    current_row += 1 # Espaçamento para linha 11 (se a tabela terminou na 10)
    bottom_block_start_row = current_row

    # --- BLOCOS INFERIORES ---
    bottom_block_rows = 10 # Altura dos blocos inferiores
    bottom_block_end_row = bottom_block_start_row + bottom_block_rows - 1

    # Bloco Esquerdo (Orientações) - A[start]:H[end]
    range_orientacoes = f"A{bottom_block_start_row}:H{bottom_block_end_row}"
    ws.merge_cells(range_orientacoes)
    orientacoes_text = "ORIENTAÇÕES:\n\n" + "\n".join([
        "1. Id. Func. em ordem crescente.",
        "2. Mapa deverá dar entrada no DE até o dia 05 de cada mês.",
        "3. Mapa atrasado do mês anterior ficará para o próximo mês, cumulativamente como do mês vigente.",
        "4. Mapas atrasados com mais de dois meses deverão ser devidamente fundamentados pelo comandante da escola, sob pena da não aceitação e restituição.",
        "5. Nos termos do item anterior, após chegar fundamentado, será adotada a medida da letra “g”, nº 5 do Item nº 3."
    ])
    _style_merged_cell(ws, bottom_block_start_row, 1, orientacoes_text, font=signature_font, alignment=left_top_align)
    _apply_border_to_range(ws, range_orientacoes, border_all) # Borda no range

    # Bloco Direito (Data e Assinaturas Aux/Digitador) - I[start]:N[end]
    range_assin_dir = f"I{bottom_block_start_row}:N{bottom_block_end_row}"
    ws.merge_cells(range_assin_dir)
    data_assinatura_str = data_fim.strftime('%d de %B de %Y') if data_fim else "____ de __________ de ____"
    # Texto formatado com mais espaço e alinhamento centralizado
    assinaturas_direita_text = f"Quartel em {cidade_assinatura} - RS, {data_assinatura_str}.\n\n\n\n\n\n" # Espaço vertical
    assinaturas_direita_text += f"____________________\tEm ___/___/___\n" # Linha e data
    assinaturas_direita_text += f"{auxiliar_nome or 'Nome Auxiliar'}\t____________\n" # Nome e linha digitador
    assinaturas_direita_text += f"{auxiliar_funcao or 'Chefe da Seção de Ensino'}\tDigitador" # Função e 'Digitador'

    _style_merged_cell(ws, bottom_block_start_row, 9, assinaturas_direita_text, font=signature_font, alignment=center_top_align)
    _apply_border_to_range(ws, range_assin_dir, border_all) # Borda no range

    # --- REMOÇÃO DAS ASSINATURAS FINAIS SOLTAS --- Confirmado que foram removidas.

    # --- FINALIZAÇÃO ---
    ws.freeze_panes = f"{main_table_start_col_letter}{table_start_row + 1}" # Congela abaixo do cabeçalho da tabela
    if data_row_end >= data_row_start:
        ws.auto_filter.ref = f"{main_table_start_col_letter}{table_start_row}:{main_table_end_col_letter}{data_row_end}" # Filtro nos dados

    # Salvar em memória
    out = BytesIO()
    wb.save(out)
    return out.getvalue()