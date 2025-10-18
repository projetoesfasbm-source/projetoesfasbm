# backend/services/relatorio_service.py

from ..models.database import db
from ..models.horario import Horario
from ..models.semana import Semana
from ..models.instrutor import Instrutor
from ..models.disciplina import Disciplina
from ..models.user import User
from sqlalchemy import select, func, and_, union_all
from sqlalchemy.orm import joinedload
from collections import defaultdict
import gspread
from google.oauth2.service_account import Credentials
from typing import Any, Dict
from datetime import datetime # Adicionado para usar data e hora

# --- Helpers ---
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
# --- Fim dos Helpers ---

class RelatorioService:
    @staticmethod
    def get_horas_aula_por_instrutor(data_inicio, data_fim, is_rr_filter=False, instrutor_ids_filter=None):
        semanas_no_periodo_ids = db.session.scalars(
            select(Semana.id).where(
                Semana.data_inicio <= data_fim,
                Semana.data_fim >= data_inicio
            )
        ).all()

        if not semanas_no_periodo_ids:
            return []

        query1 = (
            select(
                Horario.instrutor_id.label('instrutor_id'),
                Horario.disciplina_id,
                Horario.duracao
            )
            .join(Instrutor, Horario.instrutor_id == Instrutor.id)
            .where(
                Horario.semana_id.in_(semanas_no_periodo_ids),
                Horario.status == 'confirmado'
            )
        )

        query2 = (
            select(
                Horario.instrutor_id_2.label('instrutor_id'),
                Horario.disciplina_id,
                Horario.duracao
            )
            .join(Instrutor, Horario.instrutor_id_2 == Instrutor.id)
            .where(
                Horario.semana_id.in_(semanas_no_periodo_ids),
                Horario.status == 'confirmado',
                Horario.instrutor_id_2.isnot(None)
            )
        )
        
        if is_rr_filter:
            query1 = query1.where(Instrutor.is_rr == True)
            query2 = query2.where(Instrutor.is_rr == True)
        
        if instrutor_ids_filter:
            query1 = query1.where(Horario.instrutor_id.in_(instrutor_ids_filter))
            query2 = query2.where(Horario.instrutor_id_2.in_(instrutor_ids_filter))

        unioned_query = union_all(query1, query2).subquery()

        final_query = (
            select(
                unioned_query.c.instrutor_id,
                unioned_query.c.disciplina_id,
                func.sum(unioned_query.c.duracao).label('ch_a_pagar')
            )
            .group_by(unioned_query.c.instrutor_id, unioned_query.c.disciplina_id)
        )

        aulas_agrupadas = db.session.execute(final_query).all()

        if not aulas_agrupadas:
            return []
            
        instrutor_ids = {aula.instrutor_id for aula in aulas_agrupadas if aula.instrutor_id}
        
        instrutores_map = {
            i.id: i for i in db.session.scalars(
                select(Instrutor).options(joinedload(Instrutor.user)).where(Instrutor.id.in_(instrutor_ids))
            ).all()
        }
        disciplinas_map = {
            d.id: d for d in db.session.scalars(select(Disciplina)).all()
        }

        dados_formatados = defaultdict(lambda: {'info': None, 'disciplinas': []})
        for aula in aulas_agrupadas:
            instrutor = instrutores_map.get(aula.instrutor_id)
            if instrutor:
                dados_formatados[aula.instrutor_id]['info'] = instrutor
                
                disciplina_obj = disciplinas_map.get(aula.disciplina_id)
                disciplina_info = {
                    'nome': disciplina_obj.materia if disciplina_obj else "N/D",
                    'ch_total': disciplina_obj.carga_horaria_prevista if disciplina_obj else 0,
                    'ch_paga_anteriormente': disciplina_obj.carga_horaria_cumprida if disciplina_obj else 0,
                    'ch_a_pagar': float(aula.ch_a_pagar or 0)
                }
                dados_formatados[aula.instrutor_id]['disciplinas'].append(disciplina_info)
        
        resultado_final = sorted(
            [v for v in dados_formatados.values() if v['info'] and v['info'].user],
            key=lambda item: item['info'].user.nome_completo or ''
        )

        return resultado_final

    @staticmethod
    def export_to_google_sheets(contexto: Dict[str, Any]):
        """Exporta os dados do relatório para uma Planilha Google, replicando o layout do PDF."""
        try:
            PATH_CREDENCIAS_GOOGLE = '/home/esfasBM/sistema_escolar_deepseak_1/backend/credentials.json'
            ID_PLANILHA = '1ccX-mJaR109XAJg-Tykmvit6GYUaonlCkVPVPoZI3ro'
            SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

            creds = Credentials.from_service_account_file(PATH_CREDENCIAS_GOOGLE, scopes=SCOPES)
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key(ID_PLANILHA)
            
            # --- CORREÇÃO APLICADA AQUI ---
            # Cria um nome de aba único com data e hora para evitar cache.
            timestamp = datetime.now().strftime('%d-%m %H:%M')
            sheet_name = f"Mapa {contexto['nome_mes_ano']} ({timestamp})"
            
            # Adiciona uma nova aba com o nome único
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=100, cols=20)

            # --- Início da Recriação do Layout ---
            
            bold_format = {"textFormat": {"bold": True}}
            center_align = {"horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE"}
            
            # Cabeçalho Superior
            worksheet.update('B3', [[contexto['comandante_nome']]])
            worksheet.update('B4', [[contexto['comandante_funcao']]])
            worksheet.merge_cells('B3:C3'); worksheet.merge_cells('B4:C4')
            worksheet.format('B3:C4', {**center_align, "textFormat": {"bold": True, "fontSize": 11}})

            center_header_texts = [
                ["MAPA DE GRATIFICAÇÃO MAGISTÉRIO"],
                [f"OPM: {contexto['opm']}"],
                [f"Telefone: {contexto['telefone']}"],
                [f"Horas aulas a pagar do Mês de {contexto['nome_mes_ano']}"],
                [contexto['titulo_curso']]
            ]
            worksheet.update('D1', center_header_texts)
            worksheet.merge_cells('D1:K1'); worksheet.format('D1', {"textFormat": {"bold": True, "fontSize": 14}, **center_align})
            worksheet.merge_cells('D2:K2'); worksheet.format('D2', {**center_align})
            worksheet.merge_cells('D3:K3'); worksheet.format('D3', {**center_align})
            worksheet.merge_cells('D4:K4'); worksheet.format('D4', {"textFormat": {"bold": True}, **center_align})
            worksheet.merge_cells('D5:K5'); worksheet.format('D5', {"textFormat": {"bold": True}, **center_align})
            
            worksheet.update('L1', [['LANÇAR NO RHE']])
            worksheet.format('L1', {**center_align, "borders": {"top": {"style": "SOLID"}, "bottom": {"style": "SOLID"}, "left": {"style": "SOLID"}, "right": {"style": "SOLID"}}})
            worksheet.merge_cells('L1:M1')

            worksheet.update('L4', [['Ch da SEÇÃO ADM/DE']])
            worksheet.format('L4', {**center_align})
            worksheet.merge_cells('L4:M4')
            
            # Tabela Principal
            r = 7
            headers = ["Posto / Graduação", "Id. Func.", "Nome completo do servidor", "Disciplina", "CH total", "CH paga anteriormente", "CH a pagar", "Valor em R$"]
            worksheet.update(f'D{r}', [headers])
            worksheet.format(f'D{r}:K{r}', {**bold_format, **center_align, "backgroundColor": {"red": 0.85, "green": 0.85, "blue": 0.85}})

            r += 1
            table_rows = []
            total_ch_geral = 0
            total_valor_geral = 0
            
            for instrutor in contexto['dados']:
                user = _safe(instrutor, "info.user", {})
                for disc in _iter_disciplinas(instrutor):
                    ch_a_pagar = float(_safe(disc, "ch_a_pagar", 0) or 0)
                    valor = ch_a_pagar * float(contexto['valor_hora_aula'] or 0)
                    table_rows.append([
                        _safe(user, "posto_graduacao", ""), _safe(user, "matricula", ""), _safe(user, "nome_completo", ""),
                        disc.get('nome', ''), int(_safe(disc, "ch_total", 0) or 0), int(_safe(disc, "ch_paga_anteriormente", 0) or 0),
                        ch_a_pagar, valor
                    ])
                    total_ch_geral += ch_a_pagar
                    total_valor_geral += valor
            
            if table_rows:
                worksheet.update(f'D{r}', table_rows)
                r += len(table_rows)

            # Linha de Totais
            worksheet.update(f'D{r}', [["CARGA HORARIA TOTAL", "", "", "", "", "", total_ch_geral, total_valor_geral]])
            worksheet.merge_cells(f'D{r}:I{r}')
            worksheet.format(f'D{r}:K{r}', {**bold_format, "backgroundColor": {"red": 0.85, "green": 0.85, "blue": 0.85}})
            worksheet.format(f'D{r}', {"horizontalAlignment": "RIGHT"})
            worksheet.format(f'J{r}', {**center_align})
            worksheet.format(f'K{r}', {"numberFormat": {'type': 'CURRENCY', 'pattern': 'R$ #,##0.00'}, "horizontalAlignment": "RIGHT"})

            return True, worksheet.url

        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, str(e)