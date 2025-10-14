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