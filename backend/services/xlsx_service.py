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
from openpyxl.utils.cell import range_boundaries

# Configuração de locale
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
    cur = obj; # noqa: E702
    for part in path.split("."):
        if cur is None: return default; # noqa: E702
        if isinstance(cur, dict): cur = cur.get(part, default); # noqa: E702
        else: cur = getattr(cur, part, default); # noqa: E702
    return default if cur is None else cur

def _iter_disciplinas(instrutor: Any):
    if isinstance(instrutor, dict): return instrutor.get("disciplinas") or []; # noqa: E702
    return getattr(instrutor, "disciplinas", []) or []

def _apply_border_to_range(ws, cell_range_string, border_style):
    min_col, min_row, max_col, max_row = range_boundaries(cell_range_string)
    for row_idx in range(min_row, max_row + 1):
        for col_idx in range(min_col, max_col + 1):
            ws.cell(row=row_idx, column=col_idx).border = border_style

def _style_merged_cell(ws, row, col, value, font=None, alignment=None, fill=None, border=None, number_format=None, style_name=None):
    cell = ws.cell(row=row, column=col, value=value)
    if font: cell.font = font; # noqa: E702
    if alignment: cell.alignment = alignment; # noqa: E702
    if fill: cell.fill = fill; # noqa: E702
    if border: cell.border = border; # noqa: E702
    if number_format: cell.number_format = number_format; # noqa: E702
    if style_name: cell.style = style_name; # noqa: E702
    return cell

# -------------------------
# Função principal (REVISADA v11 - Replicando layout PDF)
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
    digitador_nome: Optional[str] = None, # Não presente no PDF, mas pode ser útil
    auxiliar_funcao: Optional[str] = None,
    comandante_funcao: Optional[str] = None,
    *,
    data_fim: Optional[date] = None, # Usado para data de assinatura
    cidade_assinatura: Optional[str] = "Santa Maria",
) -> bytes:
    """
    Gera arquivo .xlsx ajustado para layout A:H em A4 paisagem,
    replicando a estrutura do template PDF.
    """

    data_emissao = data_emissao or date.today() # Data de emissão geral (não usada no layout atual)
    valor_hora_aula = float(valor_hora_aula or 0)

    wb = Workbook()
    ws = wb.active
    ws.title = f"Mapa {nome_mes_ano.split(' ')[0][:3]}_{nome_mes_ano.split(' ')[-1]}"

    # Configurações de página/visual (mantidas)
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0 # Permite altura variável
    ws.page_margins = PageMargins(left=0.5, right=0.5, top=0.5, bottom=0.5) # Margens ligeiramente maiores
    ws.sheet_view.showGridLines = False

    # Definições de Layout e Colunas (A-H) - Larguras revisadas
    ws.column_dimensions['A'].width = 15 # Posto/Grad
    ws.column_dimensions['B'].width = 12 # Id. Func.
    ws.column_dimensions['C'].width = 35 # Nome Servidor
    ws.column_dimensions['D'].width = 30 # Disciplina
    ws.column_dimensions['E'].width = 9  # CH Total
    ws.column_dimensions['F'].width = 14 # CH Paga Ant
    ws.column_dimensions['G'].width = 9  # CH a pagar (Reintroduzido)
    ws.column_dimensions['H'].width = 15 # Valor R$

    # Estilos (revisados e adicionados)
    gray_fill = PatternFill("solid", fgColor="E0E0E0") # Cinza do PDF
    thin_border_side = Side(style="thin", color="000000")
    border_all = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
    border_no_top = Border(left=thin_border_side, right=thin_border_side, bottom=thin_border_side)
    border_no_bottom = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side)


    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    center_top_align = Alignment(horizontal="center", vertical="top", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
    left_top_align = Alignment(horizontal="left", vertical="top", wrap_text=True)
    right_align = Alignment(horizontal="right", vertical="center", wrap_text=True)
    right_top_align = Alignment(horizontal="right", vertical="top", wrap_text=True)


    header_font = Font(name='Times New Roman', size=10)
    header_bold_font = Font(name='Times New Roman', bold=True, size=10)
    main_title_font = Font(name='Times New Roman', bold=True, size=11) # Ligeiramente menor que 12pt
    table_header_font = Font(name='Times New Roman', bold=True, size=9)
    table_data_font = Font(name='Times New Roman', size=9)
    total_font = Font(name='Times New Roman', bold=True, size=9)
    signature_font = Font(name='Times New Roman', size=9)
    signature_bold_font = Font(name='Times New Roman', bold=True, size=9)

    brl_style_name = "BRL"
    if brl_style_name not in wb.named_styles:
        brl_style = NamedStyle(name=brl_style_name, font=table_data_font, alignment=right_align)
        brl_style.number_format = 'R$ #,##0.00' # Formato sem negativo explícito
        wb.add_named_style(brl_style)

    ch_style_name = "CH_1_DECIMAL"
    if ch_style_name not in wb.named_styles:
        ch_style = NamedStyle(name=ch_style_name, font=table_data_font, alignment=center_align)
        ch_style.number_format = '0.0'
        wb.add_named_style(ch_style)

    ch_total_style_name = "CH_TOTAL_1_DECIMAL"
    if ch_total_style_name not in wb.named_styles:
        ch_total_style = NamedStyle(name=ch_total_style_name, font=total_font, alignment=center_align, fill=gray_fill)
        ch_total_style.number_format = '0.0'
        wb.add_named_style(ch_total_style)

    brl_total_style_name = "BRL_TOTAL"
    if brl_total_style_name not in wb.named_styles:
        brl_total_style = NamedStyle(name=brl_total_style_name, font=total_font, alignment=right_align, fill=gray_fill)
        brl_total_style.number_format = 'R$ #,##0.00'
        wb.add_named_style(brl_total_style)

    # --- BLOCOS SUPERIORES E CABEÇALHO CENTRAL (Linhas 1-8) ---
    header_block_height_lines = 8 # Aumentado para dar espaço
    current_row = 1
    # Definir altura para as linhas do cabeçalho
    for i in range(current_row, current_row + header_block_height_lines):
        ws.row_dimensions[i].height = 15 # Altura padrão um pouco maior


    # Bloco Esquerdo (Comandante) - A1:B[header_block_height_lines] (Ocupa A e B)
    range_bloco_esq = f"A{current_row}:B{current_row + header_block_height_lines - 1}"
    ws.merge_cells(range_bloco_esq)
    # Aumentar espaçamento para assinatura
    assinatura_cmd_txt = f"\n\n\n\n\n________________________\n{comandante_nome or 'Nome Comandante'}\n{comandante_funcao or 'Comandante da EsFAS-SM'}"
    # Aplica borda apenas neste bloco
    _style_merged_cell(ws, current_row, 1, assinatura_cmd_txt, font=signature_bold_font, alignment=center_top_align, border=border_all)


    # Bloco Direito (RHE) - G1:H[header_block_height_lines] (Ocupa G e H)
    range_bloco_dir = f"G{current_row}:H{current_row + header_block_height_lines - 1}"
    ws.merge_cells(range_bloco_dir)
    rhe_txt = "LANÇAR NO RHE\n____/_____/_____\n\n\n\n\n____________________\nCh da SEÇÃO ADM DE"
     # Aplica borda apenas neste bloco
    _style_merged_cell(ws, current_row, 7, rhe_txt, font=signature_font, alignment=center_top_align, border=border_all)


    # Cabeçalho Central (Títulos) - C1:F[header_block_height_lines-1] (Ocupa C a F)
    # *** SEM BORDAS AQUI ***
    central_header_start_col = 3 # Coluna C
    central_header_end_col = 6   # Coluna F
    central_col_span = f"{get_column_letter(central_header_start_col)}{current_row}:{get_column_letter(central_header_end_col)}{current_row}"
    ws.merge_cells(central_col_span)
    _style_merged_cell(ws, current_row, central_header_start_col, "MAPA DE GRATIFICAÇÃO MAGISTÉRIO", font=main_title_font, alignment=center_align)
    current_row += 1
    central_col_span = f"{get_column_letter(central_header_start_col)}{current_row}:{get_column_letter(central_header_end_col)}{current_row}"
    ws.merge_cells(central_col_span)
    _style_merged_cell(ws, current_row, central_header_start_col, f"OPM: {opm_nome}", font=header_bold_font, alignment=center_align) # OPM em negrito
    current_row += 1
    central_col_span = f"{get_column_letter(central_header_start_col)}{current_row}:{get_column_letter(central_header_end_col)}{current_row}"
    ws.merge_cells(central_col_span)
    _style_merged_cell(ws, current_row, central_header_start_col, f"Telefone: {telefone or '(não informado)'}", font=header_font, alignment=center_align)
    current_row += 1
    central_col_span = f"{get_column_letter(central_header_start_col)}{current_row}:{get_column_letter(central_header_end_col)}{current_row}"
    ws.merge_cells(central_col_span)
    _style_merged_cell(ws, current_row, central_header_start_col, f"Horas aulas a pagar do Mês de {nome_mes_ano}", font=header_bold_font, alignment=center_align) # Mês em negrito
    current_row += 1
    central_col_span = f"{get_column_letter(central_header_start_col)}{current_row}:{get_column_letter(central_header_end_col)}{current_row}"
    ws.merge_cells(central_col_span)
    _style_merged_cell(ws, current_row, central_header_start_col, titulo_curso, font=header_bold_font, alignment=center_align) # Curso em negrito


    table_start_row = header_block_height_lines + 1 # Linha 9

    # --- CABEÇALHO DA TABELA PRINCIPAL --- A9:H9
    headers = [
        "Posto / graduação", "Id. Func.", "Nome completo do servidor", "Disciplina",
        "CH total", "CH paga anteriormente", "CH a pagar", "Valor em R$"
    ]
    ws.row_dimensions[table_start_row].height = 25 # Altura maior para cabeçalho da tabela
    for c_offset, text in enumerate(headers):
        col_idx = 1 + c_offset
        cell = ws.cell(table_start_row, col_idx, text)
        cell.fill = gray_fill
        cell.font = table_header_font
        cell.alignment = center_align
        cell.border = border_all
    current_row = table_start_row + 1 # Próxima linha para dados é a 10

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
                ws.row_dimensions[current_row].height = 15 # Altura padrão para dados
                for c_offset, v in enumerate(row_vals):
                    col_idx = 1 + c_offset
                    cell = ws.cell(current_row, col_idx, v)
                    cell.border = border_all
                    cell.font = table_data_font
                    if c_offset in [0, 1, 4, 5]: cell.alignment = center_align # Posto, IdFunc, CH Total, CH Paga Ant
                    elif c_offset in [2, 3]: cell.alignment = left_align # Nome, Disciplina
                    elif c_offset == 6: cell.style = "CH_1_DECIMAL" # CH a Pagar (com 1 decimal)
                    elif c_offset == 7: cell.style = "BRL" # Valor R$
                total_ch_a_pagar_sum += ch_a_pagar_val
                total_valor_sum += valor_a_pagar
                current_row += 1
    else:
        # Linha de "Nenhum dado"
        range_nodata = f"A{current_row}:H{current_row}"
        ws.merge_cells(range_nodata)
        _style_merged_cell(ws, current_row, 1, "Nenhum dado encontrado para o período e filtros selecionados.", font=table_data_font, alignment=center_align)
        _apply_border_to_range(ws, range_nodata, border_all)
        current_row += 1

    data_row_end = current_row - 1

    # --- LINHA DE TOTAIS ---
    ws.row_dimensions[current_row].height = 18 # Altura um pouco maior para totais
    range_total_label = f"A{current_row}:F{current_row}" # A até F
    ws.merge_cells(range_total_label)
    _style_merged_cell(ws, current_row, 1, "CARGA HORARIA TOTAL",
                       font=total_font, alignment=right_align, fill=gray_fill)
    _style_merged_cell(ws, current_row, 7, total_ch_a_pagar_sum, # Coluna G
                       fill=gray_fill, style_name="CH_TOTAL_1_DECIMAL")
    _style_merged_cell(ws, current_row, 8, round(total_valor_sum, 2), # Coluna H
                       fill=gray_fill, style_name="BRL_TOTAL")
    # Aplica borda manualmente em cada célula da linha total
    for col_idx in range(1, 9):
         cell = ws.cell(row=current_row, column=col_idx)
         cell.border = border_all
         if col_idx >= 7: cell.fill = gray_fill # Garante preenchimento para G e H

    current_row += 2 # Pula uma linha
    bottom_block_start_row = current_row

    # --- BLOCOS INFERIORES --- (Lado a lado A:E e F:H)
    bottom_block_rows = 10 # Número de linhas para os blocos inferiores
    bottom_block_end_row = bottom_block_start_row + bottom_block_rows - 1
    for i in range(bottom_block_start_row, bottom_block_end_row + 1):
        ws.row_dimensions[i].height = 15 # Altura para linhas do rodapé

    # Bloco Esquerdo (Orientações) - A[start]:E[end] (Ocupa 5 colunas)
    range_orientacoes = f"A{bottom_block_start_row}:E{bottom_block_end_row}"
    ws.merge_cells(range_orientacoes)
    orientacoes_text = "ORIENTAÇÕES:\n\n" + "\n".join([
        "1. Id. Func. em ordem crescente.",
        "2. Mapa deverá dar entrada no DE até o dia 05 de cada mês.",
        "3. Mapa atrasado do mês anterior ficará para o próximo mês, cumulativamente como do mês vigente.",
        "4. Mapas atrasados com mais de dois meses deverão ser devidamente fundamentados pelo comandante da escola, sob pena da não aceitação e restituição.",
        "5. Nos termos do item anterior, após chegar fundamentado, será adotada a medida da letra “g”, nº 5 do Item nº 3."
    ])
    _style_merged_cell(ws, bottom_block_start_row, 1, orientacoes_text, font=signature_font, alignment=left_top_align)
    _apply_border_to_range(ws, range_orientacoes, border_all)

    # Bloco Direito (Data e Assinaturas Aux/Digitador) - F[start]:H[end] (Ocupa 3 colunas)
    range_assin_dir = f"F{bottom_block_start_row}:H{bottom_block_end_row}"
    ws.merge_cells(range_assin_dir)
    data_assinatura_str = data_fim.strftime('%d de %B de %Y') if data_fim else "____ de __________ de ____"

    assinaturas_direita_text = f"Quartel em {cidade_assinatura} - RS, {data_assinatura_str}.\n\n\n\n\n\n" # Mais espaço vertical
    assinaturas_direita_text += "____________________                Em ___/___/___\n"
    assinaturas_direita_text += f"{auxiliar_nome or 'Nome Auxiliar'}                         ____________\n" # Ajustar espaços aqui
    assinaturas_direita_text += f"{auxiliar_funcao or 'Chefe da Seção de Ensino'}                Digitador"    # Ajustar espaços aqui

    _style_merged_cell(ws, bottom_block_start_row, 6, assinaturas_direita_text, font=signature_font, alignment=center_top_align) # Usar center_top para alinhar bloco
    _apply_border_to_range(ws, range_assin_dir, border_all)

    # --- FINALIZAÇÃO ---
    ws.freeze_panes = f"A{table_start_row + 1}" # Congela abaixo do cabeçalho da tabela
    if data_row_end >= data_row_start:
      ws.auto_filter.ref = f"A{table_start_row}:H{data_row_end}" # Filtro na tabela A:H

    # Salvar em memória
    out = BytesIO()
    wb.save(out)
    return out.getvalue()