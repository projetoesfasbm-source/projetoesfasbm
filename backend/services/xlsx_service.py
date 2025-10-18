# backend/services/xlsx_service.py

from __future__ import annotations
from io import BytesIO
from typing import Any, Iterable
from typing import Optional
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
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(part, default)
        else:
            cur = getattr(cur, part, default)
    return default if cur is None else cur


def _iter_disciplinas(instrutor: Any):
    if isinstance(instrutor, dict):
        return instrutor.get("disciplinas") or []
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
) -> bytes:␊
    """
    Gera um arquivo .xlsx nativo (OpenPyXL) com o relatório de horas-aula,
    com layout de 3 blocos conforme a imagem de referência.
    """
    data_emissao = data_emissao or date.today()

    valor_hora_aula = float(valor_hora_aula or 0)

    wb = Workbook()
    ws = wb.active
    ws.title = f"Mapa {nome_mes_ano}"

    # Configurações de página/visual
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_margins = PageMargins(left=0.2, right=0.2, top=0.4, bottom=0.4)
    ws.sheet_view.showGridLines = False

    # Definições de Layout e Colunas
    main_start_col = 4
    main_end_col = main_start_col + 7
    table_widths = [18, 14, 35, 32, 10, 22, 12, 18]
    for i, width in enumerate(table_widths):␊
        ws.column_dimensions[get_column_letter(main_start_col + i)].width = width

    # Estilos
    gray = PatternFill("solid", fgColor="D9D9D9")
    thin = Side(style="thin", color="000000")
    border_all = Border(left=thin, right=thin, top=thin, bottom=thin)
    border_outline = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    center_top = Alignment(horizontal="center", vertical="top", wrap_text=True)
    left_top = Alignment(horizontal="left", vertical="top", wrap_text=True)
    right = Alignment(horizontal="right", vertical="center", wrap_text=True)
    h1 = Font(bold=True, size=14)
    h2 = Font(size=11)
    h2_bold = Font(bold=True, size=11)
    th_font = Font(bold=True, size=10)
    total_font = Font(bold=True)
    style_name = "BRL"
    brl = next((s for s in wb.named_styles if getattr(s, "name", None) == style_name), None)
    if brl is None:
        brl = NamedStyle(name=style_name)
        brl.number_format = 'R$ #,##0.00'
        wb.add_named_style(brl)

    # Blocos Superiores
    r = 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
    c_em = ws.cell(r, 1, f"Em {data_emissao.strftime('%d/%m/%Y')}")␊
    c_em.alignment = center
    ws.merge_cells(start_row=r, start_column=12, end_row=r, end_column=14)
    c_rhe = ws.cell(r, 12, "LANÇAR NO RHE")
    c_rhe.alignment = center
    c_rhe.border = border_outline
    r += 2
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
    c_cmd_nome = ws.cell(r, 1, (comandante_nome or "NOME DO COMANDANTE"))
    c_cmd_nome.alignment = center
    c_cmd_nome.font = h2_bold
    ws.merge_cells(start_row=r+1, start_column=1, end_row=r+1, end_column=3)
    # A função do comandante no topo também pode ser dinâmica se necessário
    ws.cell(r+1, 1, (comandante_funcao or "Comandante da EsFAS")).alignment = center
    ws.merge_cells(start_row=r, start_column=12, end_row=r, end_column=14)
    ws.cell(r, 12, "/_______________________/").alignment = center
    ws.merge_cells(start_row=r+1, start_column=12, end_row=r+1, end_column=14)
    ws.cell(r+1, 12, "Ch da SEÇÃO ADM/DE").alignment = center

    # Cabeçalho Textual Central
    r = 1
    ws.merge_cells(start_row=r, start_column=main_start_col, end_row=r, end_column=main_end_col)
    ws.cell(r, main_start_col, "MAPA DE GRATIFICAÇÃO MAGISTÉRIO").font = h1
    ws.cell(r, main_start_col).alignment = center
    r += 1
    opm_escola_str = f"OPM: {opm_nome} - {escola_nome}"
    ws.merge_cells(start_row=r, start_column=main_start_col, end_row=r, end_column=main_end_col)
    ws.cell(r, main_start_col, opm_escola_str).font = h2
    ws.cell(r, main_start_col).alignment = center
    r += 1
    ws.merge_cells(start_row=r, start_column=main_start_col, end_row=r, end_column=main_end_col)
    texto_telefone = f"Telefone: {telefone}" if telefone else "Telefone: (não informado)"
    ws.cell(r, main_start_col, texto_telefone).font = h2
    ws.cell(r, main_start_col).alignment = center
    r += 1
    ws.merge_cells(start_row=r, start_column=main_start_col, end_row=r, end_column=main_end_col)
    ws.cell(r, main_start_col, f"Horas aulas a pagar do Mês de {nome_mes_ano}").font = h2_bold
    ws.cell(r, main_start_col).alignment = center
    r += 1
    ws.merge_cells(start_row=r, start_column=main_start_col, end_row=r, end_column=main_end_col)
    ws.cell(r, main_start_col, titulo_curso).font = h2_bold
    ws.cell(r, main_start_col).alignment = center
    r += 2

    # Cabeçalho da tabela
    headers = [
        "Posto / graduação",
        "Matrícula",
        "Nome completo do servidor",
        "Disciplina",
        "CH total",
        "CH paga anteriormente no acumulado dos mapas",
        "CH a pagar",
        "Valor em R$ CH a Pagar",
    ]
    start_table_row = r
    for c_offset, text in enumerate(headers):␊
        cell = ws.cell(r, main_start_col + c_offset, text)␊
        cell.fill = gray
        cell.font = th_font
        cell.alignment = center
        cell.border = border_all
    r += 1

    # Linhas de dados
    total_ch_a_pagar = 0␊
    total_valor = 0.0␊
    last_data_row = None
    for instrutor in (dados or []):
        user = _safe(instrutor, "info.user", {})
        for disc in _iter_disciplinas(instrutor):
            row_vals = [
                _safe(user, "posto_graduacao", "N/D"), _safe(user, "matricula", ""),
                _safe(user, "nome_completo", ""), _safe(disc, "nome", ""),
                int(_safe(disc, "ch_total", 0) or 0),
                int(_safe(disc, "ch_paga_anteriormente", 0) or 0),
                int(_safe(disc, "ch_a_pagar", 0) or 0),
                float(int(_safe(disc, "ch_a_pagar", 0) or 0)) * valor_hora_aula,
            ]
            for c_offset, v in enumerate(row_vals):
                c = main_start_col + c_offset
                cell = ws.cell(r, c, v)
                cell.border = border_all
                if c_offset in (0, 1, 4, 5, 6):
                    cell.alignment = center
                elif c_offset in (2, 3):
                    cell.alignment = Alignment(horizontal="left", vertical="center")
                elif c_offset == 7:
                    cell.style = brl
                    cell.alignment = right
            total_ch_a_pagar += row_vals[6]
            total_valor += row_vals[7]
            last_data_row = r
            r += 1
    total_valor = round(total_valor, 2)
    if not last_data_row:
        ws.merge_cells(start_row=r, start_column=main_start_col, end_row=r, end_column=main_end_col)
        cell = ws.cell(r, main_start_col, "Nenhum dado encontrado para o período e filtros selecionados.")
        cell.alignment = center
        cell.border = border_all
        last_data_row = r
        r += 1

    # Rodapé com totais
    ws.merge_cells(start_row=r, start_column=main_start_col, end_row=r, end_column=main_end_col - 2)
    c_tot_label = ws.cell(r, main_start_col, "CARGA HORÁRIA TOTAL")
    c_tot_label.fill = gray
    c_tot_label.font = total_font
    c_tot_label.alignment = right
    c_tot_ch = ws.cell(r, main_end_col - 1, total_ch_a_pagar)
    c_tot_ch.alignment = center
    c_tot_ch.font = total_font
    c_tot_ch.fill = gray
    c_tot_vl = ws.cell(r, main_end_col, total_valor)
    c_tot_vl.style = brl
    c_tot_vl.alignment = right
    c_tot_vl.font = total_font
    c_tot_vl.fill = gray
    for i in range(main_start_col, main_end_col + 1):
        ws.cell(r, i).border = border_all
    r += 1

    # Bloco ORIENTAÇÕES e lateral
    ori_lines = [
        "1.  Id. Func. em ordem crescente.",
        "2.  Mapa deverá dar entrada no DE até o dia 05 de cada mês.",
        "3.  Mapa atrasado do mês anterior ficará para o próximo mês, cumulativamente como do mês vigente.",
        "4.  Mapas atrasados com mais de dois meses deverão ser devidamente fundamentados pelo comandante da escola, sob pena da não aceitação e restituição.",
        "5.  Nos termos do item anterior, após chegar fundamentado, será adotada a medida da letra “g”, nº 5 do Item nº 3.",
    ]
    left_text = "ORIENTAÇÕES:\n\n" + "\n".join(ori_lines)
    data_fmt = data_fim.strftime("%d de %B de %Y") if data_fim else "____ de __________ de ____"
    right_text = dedent(f"""Quartel em {cidade_assinatura}, {data_fmt}.\nDigitado\nEm ____/____/_____\n\n____________________\n{digitador_nome or 'digitador'}""").strip()
    block_rows = 10
    left_start_row = r
    left_end_row = r + block_rows - 1
    ws.merge_cells(start_row=left_start_row, start_column=1, end_row=left_end_row, end_column=8)
    c_left = ws.cell(left_start_row, 1, left_text)
    c_left.alignment = left_top
    ws.merge_cells(start_row=left_start_row, start_column=9, end_row=left_end_row, end_column=14)
    c_right = ws.cell(left_start_row, 9, right_text)
    c_right.alignment = center_top
    for row_idx in range(left_start_row, left_end_row + 1):
        for col_idx in range(1, 15):␊
            ws.cell(row_idx, col_idx).border = border_outline
    r = left_end_row + 2

    # -------------------------
    # Assinaturas Finais
    # -------------------------
    # Linha de assinatura
    ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=6)
    ws.cell(r, 4, "____________________________________").alignment = center
    ws.merge_cells(start_row=r, start_column=8, end_row=r, end_column=10)
    ws.cell(r, 8, "____________________________________").alignment = center
    r += 1
    # Linha com os Nomes
    ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=6)
    ws.cell(r, 4, (auxiliar_nome or "")).alignment = center
    ws.merge_cells(start_row=r, start_column=8, end_row=r, end_column=10)
    ws.cell(r, 8, (comandante_nome or "")).alignment = center
    r += 1
    # Linha com as Funções/Cargos
    ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=6)
    ws.cell(r, 4, (auxiliar_funcao or "Auxiliar da Seção de Ensino")).alignment = center
    ws.merge_cells(start_row=r, start_column=8, end_row=r, end_column=10)
    ws.cell(r, 8, (comandante_funcao or "Comandante da EsFAS")).alignment = center
    # -------------------------

    # Congelar painéis e filtro
    ws.freeze_panes = f"{get_column_letter(main_start_col)}{start_table_row+1}"
    if last_data_row:
        ws.auto_filter.ref = f"{get_column_letter(main_start_col)}{start_table_row}:{get_column_letter(main_end_col)}{last_data_row}"

    # Salvar em memória
    out = BytesIO()
    wb.save(out)␊
    return out.getvalue()