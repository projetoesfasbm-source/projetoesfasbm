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

# --- Helpers do XLSX Service movidos para cá ---
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
            query1 = query1.join(User, Instrutor.user_id == User.id).where(User.is_rr == True)
            query2 = query2.join(User, Instrutor.user_id == User.id).where(User.is_rr == True)
        
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
            
        instrutor_ids = {aula.instrutor_id for aula in aulas_agrupadas}
        
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
            dados_formatados.values(),
            key=lambda item: item['info'].user.nome_completo or ''
        )

        return resultado_final

    @staticmethod
    def export_to_google_sheets(dados, valor_hora_aula, nome_mes_ano):
        """Exporta os dados do relatório para uma Planilha Google."""
        try:
            # --- Configurações da Planilha (baseado no seu script export_to_sheets.py) ---
            PATH_CREDENCIAS_GOOGLE = '/home/esfasBM/sistema_escolar_deepseak_1/backend/credentials.json'
            ID_PLANILHA = '16X3qOihCsB-pSnqi7ZUYD0r3_MwV1toKWuP30xYtSoQ'
            SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

            # 1. Autenticação
            creds = Credentials.from_service_account_file(PATH_CREDENCIAS_GOOGLE, scopes=SCOPES)
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key(ID_PLANILHA)
            
            # 2. Prepara ou cria a aba (worksheet)
            sheet_name = f"Mapa {nome_mes_ano}"
            try:
                worksheet = spreadsheet.worksheet(sheet_name)
                worksheet.clear() # Limpa a aba se ela já existir
            except gspread.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=100, cols=20)

            # 3. Formata os dados para a planilha
            headers = ["Posto / Graduação", "Id. Func.", "Nome Completo", "Disciplina", "CH Total", "CH Paga Anteriormente", "CH a Pagar", "Valor em R$"]
            rows = [headers]
            total_ch_geral = 0
            total_valor_geral = 0

            for instrutor in dados:
                user = _safe(instrutor, "info.user", {})
                for disc in _iter_disciplinas(instrutor):
                    ch_a_pagar = float(_safe(disc, "ch_a_pagar", 0) or 0)
                    valor = ch_a_pagar * valor_hora_aula
                    rows.append([
                        _safe(user, "posto_graduacao", ""),
                        _safe(user, "matricula", ""),
                        _safe(user, "nome_completo", ""),
                        disc.get('nome', ''),
                        _safe(disc, "ch_total", 0),
                        _safe(disc, "ch_paga_anteriormente", 0),
                        ch_a_pagar,
                        valor
                    ])
                    total_ch_geral += ch_a_pagar
                    total_valor_geral += valor
            
            # Adiciona a linha de totais
            rows.append(['', '', '', '', '', 'CARGA HORÁRIA TOTAL', total_ch_geral, total_valor_geral])

            # 4. Envia os dados para a planilha
            worksheet.update('A1', rows)
            
            # 5. Formatação (opcional, mas melhora a aparência)
            worksheet.format('A1:H1', {'textFormat': {'bold': True}, 'horizontalAlignment': 'CENTER'})
            worksheet.format(f'G{len(rows)}:H{len(rows)}', {'textFormat': {'bold': True}})
            worksheet.format(f'H2:H{len(rows)}', {'numberFormat': {'type': 'CURRENCY', 'pattern': 'R$ #,##0.00'}})

            return True, worksheet.url

        except Exception as e:
            return False, str(e)