# backend/services/xlsx_service.py

from __future__ import annotations
from io import BytesIO
from typing import Any, Iterable, Optional
from datetime import date
from textwrap import dedent

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side, NamedStyle
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins


__all__ = ["gerar_mapa_gratificacao_xlsx"]


# -------------------------
# Helpers
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
    data_emissao: date,
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
    Gera um arquivo .xlsx nativo (OpenPyXL) com o relatório de horas-aula,
    com layout de 3 blocos conforme a imagem de referência.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = f"Mapa {nome_mes_ano}"

    # Configurações de página/visual
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_margins = PageMargins(left=0.25, right=0.25, top=0.5, bottom=0.5)
    ws.sheet_view.showGridLines = False

    # Definições de Layout e Colunas
    ws.column_dimensions['B'].width = 30
    ws.column_dimensions['D'].width = 20
    ws.column_dimensions['E'].width = 15
    ws.column_dimensions['F'].width = 38
    ws.column_dimensions['G'].width = 38
    ws.column_dimensions['H'].width = 8
    ws.column_dimensions['I'].width = 22
    ws.column_dimensions['J'].width = 8
    ws.column_dimensions['K'].width = 18
    ws.column_dimensions['L'].width = 15
    ws.column_dimensions['M'].width = 15

    # Estilos
    gray_fill = PatternFill("solid", fgColor="D9D9D9")
    thin_side = Side(style="thin", color="000000")
    border_all = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
    border_bottom = Border(bottom=thin_side)
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
    right_align = Alignment(horizontal="right", vertical="center", wrap_text=True)

    h1_font = Font(bold=True, size=14)
    h2_font = Font(size=11)
    h2_bold_font = Font(bold=True, size=11)
    th_font = Font(bold=True, size=10)
    total_font = Font(bold=True)
    brl_style_name = "BRL"
    if brl_style_name not in wb.style_names:
        brl_style = NamedStyle(name=brl_style_name, number_format='R$ #,##0.00')
        wb.add_named_style(brl_style)

    # --- CABEÇALHO SUPERIOR ---
    # Bloco Esquerdo (Assinatura Comandante)
    ws.cell(row=3, column=2, value=comandante_nome).font = h2_bold_font
    ws.cell(row=3, column=2).alignment = center_align
    ws.merge_cells(start_row=3, start_column=2, end_row=3, end_column=3)
    
    ws.cell(row=4, column=2, value=comandante_funcao).alignment = center_align
    ws.merge_cells(start_row=4, start_column=2, end_row=4, end_column=3)

    # Bloco Central (Título)
    ws.cell(row=1, column=4, value="MAPA DE GRATIFICAÇÃO MAGISTÉRIO").font = h1_font
    ws.cell(row=1, column=4).alignment = center_align
    ws.merge_cells(start_row=1, start_column=4, end_row=1, end_column=11)
    
    texts = [f"OPM: {opm_nome}", f"Telefone: {telefone}", f"Horas aulas a pagar do Mês de {nome_mes_ano}", titulo_curso]
    for i, text in enumerate(texts):
        r = i + 2
        cell = ws.cell(row=r, column=4, value=text)
        cell.font = h2_bold_font if "Horas aulas" in text or titulo_curso in text else h2_font
        cell.alignment = center_align
        ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=11)
    
    # Bloco Direito (Lançar no RHE)
    cell = ws.cell(row=1, column=12, value="LANÇAR NO RHE")
    cell.border = border_all
    cell.alignment = center_align
    ws.merge_cells(start_row=1, start_column=12, end_row=1, end_column=13)
    
    ws.cell(row=3, column=12).border = border_bottom
    ws.merge_cells(start_row=3, start_column=12, end_row=3, end_column=13)

    cell = ws.cell(row=4, column=12, value="Ch da SEÇÃO ADM/DE")
    cell.alignment = center_align
    ws.merge_cells(start_row=4, start_column=12, end_row=4, end_column=13)

    # --- TABELA PRINCIPAL ---
    r = 7 
    headers = ["Posto / graduação", "Id. Func.", "Nome completo do servidor", "Disciplina", "CH total", "CH paga anteriormente", "CH a pagar", "Valor em R$"]
    for c_offset, text in enumerate(headers):
        cell = ws.cell(row=r, column=4 + c_offset, value=text)
        cell.fill = gray_fill
        cell.font = th_font
        cell.alignment = center_align
        cell.border = border_all
    r += 1
    
    total_ch_a_pagar = 0
    total_valor = 0.0
    for instrutor in (dados or []):
        user = _safe(instrutor, "info.user", {})
        for disc in _iter_disciplinas(instrutor):
            ch_a_pagar = float(_safe(disc, "ch_a_pagar", 0) or 0)
            valor_a_pagar = ch_a_pagar * float(valor_hora_aula or 0)
            row_data = [
                _safe(user, "posto_graduacao", "N/D"), _safe(user, "matricula", ""),
                _safe(user, "nome_completo", ""), _safe(disc, "nome", ""),
                int(_safe(disc, "ch_total", 0) or 0), int(_safe(disc, "ch_paga_anteriormente", 0) or 0),
                ch_a_pagar, valor_a_pagar,
            ]
            for c_offset, value in enumerate(row_data):
                cell = ws.cell(r, 4 + c_offset, value)
                cell.border = border_all
                if c_offset in [0, 1, 4, 5, 6]: cell.alignment = center_align
                elif c_offset in [2, 3]: cell.alignment = left_align
                elif c_offset == 7:
                    cell.style = brl_style_name
                    cell.alignment = right_align
            
            total_ch_a_pagar += ch_a_pagar
            total_valor += valor_a_pagar
            r += 1
    
    # Linha de Totais
    cell = ws.cell(row=r, column=4, value="CARGA HORARIA TOTAL")
    cell.fill = gray_fill
    cell.font = total_font
    cell.alignment = right_align
    ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=9)
    
    cell = ws.cell(row=r, column=10, value=total_ch_a_pagar)
    cell.fill = gray_fill
    cell.font = total_font
    cell.alignment = center_align
    
    cell = ws.cell(row=r, column=11, value=total_valor)
    cell.fill = gray_fill
    cell.font = total_font
    cell.alignment = right_align
    cell.style = brl_style_name
    
    for c in range(4, 12):
        ws.cell(r, c).border = border_all
    r += 2

    # --- BLOCO INFERIOR ---
    start_footer_row = r
    # Bloco Esquerdo: ORIENTAÇÕES
    ori_lines = ["1. Id. Func. em ordem crescente.", "2. Mapa deverá dar entrada no DE até o dia 05 de cada mês.", "3. Mapa atrasado do mês anterior ficará para o próximo mês, cumulativamente como do mês vigente.", "4. Mapas atrasados com mais de dois meses deverão ser devidamente fundamentados pelo comandante da escola, sob pena da não aceitação e restituição.", "5. Nos termos do item anterior, após chegar fundamentado, será adotada a medida da letra “g”, nº 5 do Item nº 3."]
    left_text = "ORIENTAÇÕES:\n" + "\n".join(ori_lines)
    cell = ws.cell(row=start_footer_row, column=1, value=left_text)
    cell.alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
    ws.merge_cells(start_row=start_footer_row, start_column=1, end_row=start_footer_row+9, end_column=8)

    # Bloco Direito: Data e Assinaturas
    data_fmt = data_fim.strftime("%d de %B de %Y") if data_fim else "____ de __________ de ____"
    cell = ws.cell(row=start_footer_row, column=10, value=f"Quartel em {cidade_assinatura}, {data_fmt}.")
    cell.alignment = center_align
    ws.merge_cells(start_row=start_footer_row, start_column=10, end_row=start_footer_row, end_column=13)
    
    # Assinatura do Auxiliar
    aux_sig_row = start_footer_row + 8
    ws.cell(row=aux_sig_row, column=2).border = border_bottom
    ws.merge_cells(start_row=aux_sig_row, start_column=2, end_row=aux_sig_row, end_column=5)
    
    cell = ws.cell(row=aux_sig_row + 1, column=2, value=auxiliar_nome)
    cell.alignment = center_align
    ws.merge_cells(start_row=aux_sig_row + 1, start_column=2, end_row=aux_sig_row + 1, end_column=5)

    cell = ws.cell(row=aux_sig_row + 2, column=2, value=auxiliar_funcao)
    cell.alignment = center_align
    ws.merge_cells(start_row=aux_sig_row + 2, start_column=2, end_row=aux_sig_row + 2, end_column=5)

    # Assinatura do Digitador
    dig_sig_row = aux_sig_row - 1
    cell = ws.cell(row=dig_sig_row, column=11, value="Em _____/_____/_____")
    cell.alignment = center_align
    ws.merge_cells(start_row=dig_sig_row, start_column=11, end_row=dig_sig_row, end_column=13)
    
    ws.cell(row=dig_sig_row + 1, column=11).border = border_bottom
    ws.merge_cells(start_row=dig_sig_row + 1, start_column=11, end_row=dig_sig_row + 1, end_column=13)
    
    cell = ws.cell(row=dig_sig_row + 2, column=11, value=digitador_nome or "Digitador")
    cell.alignment = center_align
    ws.merge_cells(start_row=dig_sig_row + 2, start_column=11, end_row=dig_sig_row + 2, end_column=13)
    
    # Salvar em memória
    out = BytesIO()
    wb.save(out)
    return out.getvalue()