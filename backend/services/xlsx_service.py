# backend/services/xlsx_service.py

from __future__ import annotations
from io import BytesIO
from typing import Any, Iterable
from typing import Optional
from datetime import date
from textwrap import dedent
import locale
import openpyxl

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
        locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil')  # Windows
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, '')  # Usa o padrão do sistema
        except locale.Error:
            print("Aviso: Não foi possível definir o locale para pt_BR ou padrão do sistema.")

__all__ = ["gerar_mapa_gratificacao_xlsx"]

# -------------------------
# Helpers
# -------------------------
def _safe(obj: Any, path: str, default: Any = None) -> Any:
    """Acessa de forma segura atributos ou chaves aninhadas."""
    cur = obj
    for part in path.split("."):
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(part, default)
        else:
            cur = getattr(cur, part, default)
    return default if cur is None else cur

def _iter_disciplinas(instrutor: Any):
    """Itera sobre as disciplinas de um instrutor."""
    if isinstance(instrutor, dict):
        return instrutor.get("disciplinas") or []
    return getattr(instrutor, "disciplinas", []) or []

def _apply_border_to_range(ws, cell_range_string, border_style):
    """Aplica borda a um intervalo de células."""
    min_col, min_row, max_col, max_row = range_boundaries(cell_range_string)
    for row_idx in range(min_row, max_row + 1):
        for col_idx in range(min_col, max_col + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            if cell.border is None:
                cell.border = border_style
            else:
                # Preserva bordas existentes e adiciona as novas
                existing_border = cell.border
                new_border = Border(
                    left=border_style.left or existing_border.left,
                    right=border_style.right or existing_border.right,
                    top=border_style.top or existing_border.top,
                    bottom=border_style.bottom or existing_border.bottom
                )
                cell.border = new_border

def _style_merged_cell(ws, row, col, value, font=None, alignment=None, fill=None, border=None, number_format=None, style_name=None):
    """Estiliza uma célula mesclada."""
    cell = ws.cell(row=row, column=col, value=value)
    if font:
        cell.font = font
    if alignment:
        cell.alignment = alignment
    if fill:
        cell.fill = fill
    if border:
        cell.border = border
    if number_format:
        cell.number_format = number_format
    if style_name:
        cell.style = style_name
    return cell

def _apply_specific_borders(ws, thin_side):
    """Aplica bordas específicas no cabeçalho conforme solicitado."""
    # Borda superior da linha 1 entre colunas A-H
    for col in range(1, 9):
        cell = ws.cell(1, col)
        current_border = cell.border or Border()
        cell.border = Border(
            top=thin_side,
            left=current_border.left,
            right=current_border.right,
            bottom=current_border.bottom
        )
    
    # Bordas laterais específicas
    for row in range(1, 9):  # Linhas 1 a 8
        # Borda lateral esquerda coluna A
        cell_a = ws.cell(row, 1)
        current_border_a = cell_a.border or Border()
        cell_a.border = Border(
            top=current_border_a.top,
            left=thin_side,
            right=current_border_a.right,
            bottom=current_border_a.bottom
        )
        
        # Borda lateral direita coluna B
        cell_b = ws.cell(row, 2)
        current_border_b = cell_b.border or Border()
        cell_b.border = Border(
            top=current_border_b.top,
            left=current_border_b.left,
            right=thin_side,
            bottom=current_border_b.bottom
        )
        
        # Borda lateral esquerda coluna G
        cell_g = ws.cell(row, 7)
        current_border_g = cell_g.border or Border()
        cell_g.border = Border(
            top=current_border_g.top,
            left=thin_side,
            right=current_border_g.right,
            bottom=current_border_g.bottom
        )
        
        # Borda lateral direita coluna H
        cell_h = ws.cell(row, 8)
        current_border_h = cell_h.border or Border()
        cell_h.border = Border(
            top=current_border_h.top,
            left=current_border_h.left,
            right=thin_side,
            bottom=current_border_h.bottom
        )

# -------------------------
# Função principal
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
    Gera arquivo .xlsx com bordas específicas no cabeçalho para replicar o layout do PDF.
    """

    data_emissao = data_emissao or date.today()
    valor_hora_aula = float(valor_hora_aula or 0)

    wb = Workbook()
    ws = wb.active
    ws.title = f"Mapa {nome_mes_ano.split(' ')[0][:3]}_{nome_mes_ano.split(' ')[-1]}"

    # Configuração da página
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_margins = PageMargins(left=0.5, right=0.5, top=0.5, bottom=0.5)
    ws.sheet_view.showGridLines = False

    # Configuração das colunas
    ws.column_dimensions['A'].width = 15
    ws.column_dimensions['B'].width = 12
    ws.column_dimensions['C'].width = 35
    ws.column_dimensions['D'].width = 30
    ws.column_dimensions['E'].width = 9
    ws.column_dimensions['F'].width = 14
    ws.column_dimensions['G'].width = 9
    ws.column_dimensions['H'].width = 15

    # Estilos
    gray_fill = PatternFill("solid", fgColor="E0E0E0")
    thin_side = Side(style="thin", color="000000")
    border_all = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
    
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    center_top_align = Alignment(horizontal="center", vertical="top", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
    left_top_align = Alignment(horizontal="left", vertical="top", wrap_text=True)
    right_align = Alignment(horizontal="right", vertical="center", wrap_text=True)
    
    header_font = Font(name='Times New Roman', size=10)
    header_bold_font = Font(name='Times New Roman', bold=True, size=10)
    main_title_font = Font(name='Times New Roman', bold=True, size=11)
    table_header_font = Font(name='Times New Roman', bold=True, size=9)
    table_data_font = Font(name='Times New Roman', size=9)
    total_font = Font(name='Times New Roman', bold=True, size=9)
    signature_font = Font(name='Times New Roman', size=9)
    signature_bold_font = Font(name='Times New Roman', bold=True, size=9)

    # Estilos nomeados
    if "BRL" not in wb.named_styles:
        brl_style = NamedStyle(name="BRL", font=table_data_font, alignment=right_align, number_format='R$ #,##0.00')
        wb.add_named_style(brl_style)
    if "CH_1_DECIMAL" not in wb.named_styles:
        ch_style = NamedStyle(name="CH_1_DECIMAL", font=table_data_font, alignment=center_align, number_format='0.0')
        wb.add_named_style(ch_style)
    if "CH_TOTAL_1_DECIMAL" not in wb.named_styles:
        ch_total_style = NamedStyle(name="CH_TOTAL_1_DECIMAL", font=total_font, alignment=center_align, fill=gray_fill, number_format='0.0')
        wb.add_named_style(ch_total_style)
    if "BRL_TOTAL" not in wb.named_styles:
        brl_total_style = NamedStyle(name="BRL_TOTAL", font=total_font, alignment=right_align, fill=gray_fill, number_format='R$ #,##0.00')
        wb.add_named_style(brl_total_style)

    # --- CABEÇALHO SUPERIOR (Linhas 1-8) ---
    header_block_height_lines = 8
    current_row = 1
    
    # Configurar altura das linhas do cabeçalho
    for i in range(current_row, current_row + header_block_height_lines):
        ws.row_dimensions[i].height = 15

    # Bloco Esquerdo (Comandante)
    range_bloco_esq = f"A{current_row}:B{current_row + header_block_height_lines - 1}"
    ws.merge_cells(range_bloco_esq)
    assinatura_cmd_txt = f"\n\n\n\n\n________________________\n{comandante_nome or 'Nome Comandante'}\n{comandante_funcao or 'Comandante da EsFAS-SM'}"
    _style_merged_cell(ws, current_row, 1, assinatura_cmd_txt, font=signature_bold_font, alignment=center_top_align)

    # Bloco Direito (RHE)
    range_bloco_dir = f"G{current_row}:H{current_row + header_block_height_lines - 1}"
    ws.merge_cells(range_bloco_dir)
    rhe_txt = "LANÇAR NO RHE\n____/_____/_____\n\n\n\n\n____________________\nCh da SEÇÃO ADM DE"
    _style_merged_cell(ws, current_row, 7, rhe_txt, font=signature_font, alignment=center_top_align)

    # Cabeçalho Central (Títulos)
    ws.merge_cells(f"C{current_row}:F{current_row}")
    _style_merged_cell(ws, current_row, 3, "MAPA DE GRATIFICAÇÃO MAGISTÉRIO", font=main_title_font, alignment=center_align)
    current_row += 1
    
    ws.merge_cells(f"C{current_row}:F{current_row}")
    _style_merged_cell(ws, current_row, 3, f"OPM: {opm_nome}", font=header_bold_font, alignment=center_align)
    current_row += 1
    
    ws.merge_cells(f"C{current_row}:F{current_row}")
    _style_merged_cell(ws, current_row, 3, f"Telefone: {telefone or '(não informado)'}", font=header_font, alignment=center_align)
    current_row += 1
    
    ws.merge_cells(f"C{current_row}:F{current_row}")
    _style_merged_cell(ws, current_row, 3, f"Horas aulas a pagar do Mês de {nome_mes_ano}", font=header_bold_font, alignment=center_align)
    current_row += 1
    
    ws.merge_cells(f"C{current_row}:F{current_row}")
    _style_merged_cell(ws, current_row, 3, titulo_curso, font=header_bold_font, alignment=center_align)

    # --- APLICAÇÃO DAS BORDAS ESPECÍFICAS NO CABEÇALHO ---
    _apply_specific_borders(ws, thin_side)

    # --- TABELA PRINCIPAL ---
    table_start_row = header_block_height_lines + 1

    # Cabeçalho da tabela
    headers = ["Posto / graduação", "Id. Func.", "Nome completo do servidor", "Disciplina", "CH total", "CH paga anteriormente", "CH a pagar", "Valor em R$"]
    ws.row_dimensions[table_start_row].height = 25
    
    for c_offset, text in enumerate(headers):
        col_idx = 1 + c_offset
        cell = ws.cell(table_start_row, col_idx, text)
        cell.fill = gray_fill
        cell.font = table_header_font
        cell.alignment = center_align
        cell.border = border_all

    current_row = table_start_row + 1

    # Dados da tabela
    total_ch_a_pagar_sum = 0
    total_valor_sum = 0.0
    
    if dados:
        for instrutor in dados:
            user = _safe(instrutor, "info.user", {})
            for disc in _iter_disciplinas(instrutor):
                ch_a_pagar_val = float(_safe(disc, "ch_a_pagar", 0) or 0)
                valor_a_pagar = ch_a_pagar_val * valor_hora_aula
                
                row_vals = [
                    _safe(user, "posto_graduacao", "N/D"),
                    _safe(user, "matricula", ""),
                    _safe(user, "nome_completo", ""),
                    _safe(disc, "nome", ""),
                    float(_safe(disc, "ch_total", 0) or 0),
                    float(_safe(disc, "ch_paga_anteriormente", 0) or 0),
                    ch_a_pagar_val,
                    round(valor_a_pagar, 2)
                ]
                
                ws.row_dimensions[current_row].height = 15
                
                for c_offset, v in enumerate(row_vals):
                    col_idx = 1 + c_offset
                    cell = ws.cell(current_row, col_idx, v)
                    cell.border = border_all
                    cell.font = table_data_font
                    
                    if c_offset in [0, 1, 4, 5]:
                        cell.alignment = center_align
                    elif c_offset in [2, 3]:
                        cell.alignment = left_align
                    elif c_offset == 6:
                        cell.style = "CH_1_DECIMAL"
                    elif c_offset == 7:
                        cell.style = "BRL"
                
                total_ch_a_pagar_sum += ch_a_pagar_val
                total_valor_sum += valor_a_pagar
                current_row += 1
    else:
        # Linha para quando não há dados
        ws.merge_cells(f"A{current_row}:H{current_row}")
        _style_merged_cell(ws, current_row, 1, "Nenhum dado encontrado...", 
                          font=table_data_font, alignment=center_align, border=border_all)
        current_row += 1

    # --- LINHA DE TOTAIS ---
    ws.row_dimensions[current_row].height = 18
    ws.merge_cells(f"A{current_row}:F{current_row}")
    _style_merged_cell(ws, current_row, 1, "CARGA HORARIA TOTAL", 
                      font=total_font, alignment=right_align, fill=gray_fill)
    
    _style_merged_cell(ws, current_row, 7, total_ch_a_pagar_sum, 
                      style_name="CH_TOTAL_1_DECIMAL")
    _style_merged_cell(ws, current_row, 8, round(total_valor_sum, 2), 
                      style_name="BRL_TOTAL")
    
    _apply_border_to_range(ws, f"A{current_row}:H{current_row}", border_all)

    current_row += 2

    # --- BLOCOS INFERIORES ---
    bottom_block_start_row = current_row
    bottom_block_rows = 10
    bottom_block_end_row = bottom_block_start_row + bottom_block_rows - 1
    
    # Configurar altura das linhas dos blocos inferiores
    for i in range(bottom_block_start_row, bottom_block_end_row + 1):
        ws.row_dimensions[i].height = 15

    # Bloco Esquerdo (Orientações)
    range_orientacoes = f"A{bottom_block_start_row}:E{bottom_block_end_row}"
    ws.merge_cells(range_orientacoes)
    orientacoes_text = "ORIENTAÇÕES:\n\n" + "\n".join([
        "1. Id. Func. em ordem crescente.",
        "2. Mapa deverá dar entrada no DE até o dia 05 de cada mês.",
        "3. Mapa atrasado do mês anterior ficará para o próximo mês, cumulativamente como do mês vigente.",
        "4. Mapas atrasados com mais de dois meses deverão ser devidamente fundamentados pelo comandante da escola, sob pena da não aceitação e restituição.",
        "5. Nos termos do item anterior, após chegar fundamentado, será adotada a medida da letra 'g', nº 5 do Item nº 3."
    ])
    _style_merged_cell(ws, bottom_block_start_row, 1, orientacoes_text, 
                      font=signature_font, alignment=left_top_align, border=border_all)

    # Bloco Direito (Assinaturas)
    range_assin_dir = f"F{bottom_block_start_row}:H{bottom_block_end_row}"
    ws.merge_cells(range_assin_dir)
    
    data_assinatura_str = data_fim.strftime('%d de %B de %Y') if data_fim else "____ de __________ de ____"
    assinaturas_direita_text = f"Quartel em {cidade_assinatura} - RS, {data_assinatura_str}.\n\n\n\n\n\n"
    assinaturas_direita_text += "____________________                Em ___/___/___\n"
    assinaturas_direita_text += f"{auxiliar_nome or 'Nome Auxiliar'}                         ____________\n"
    assinaturas_direita_text += f"{auxiliar_funcao or 'Chefe da Seção de Ensino'}                Digitador"
    
    _style_merged_cell(ws, bottom_block_start_row, 6, assinaturas_direita_text, 
                      font=signature_font, alignment=center_top_align, border=border_all)

    # --- FINALIZAÇÃO ---
    ws.freeze_panes = f"A{table_start_row + 1}"
    
    if dados:
        ws.auto_filter.ref = f"A{table_start_row}:H{current_row - 3}"

    # Gerar arquivo em memória
    out = BytesIO()
    wb.save(out)
    return out.getvalue()