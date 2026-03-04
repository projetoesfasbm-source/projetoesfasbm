# backend/services/disciplina_service.py

from flask import current_app
from sqlalchemy import select, func, distinct, case, or_
from ..models.database import db
from ..models.disciplina import Disciplina
from ..models.disciplina_turma import DisciplinaTurma
from ..models.horario import Horario
from ..models.turma import Turma
from ..models.ciclo import Ciclo
from ..models.semana import Semana

class DisciplinaService:
    
    @staticmethod
    def get_dados_progresso(disciplina):
        """
        Calcula o progresso de uma disciplina específica com partições:
        Concluído (Cumprido), Agendado (No Quadro de Horários) e Restante.
        """
        try:
            previsto = disciplina.carga_horaria_prevista
            realizado = disciplina.carga_horaria_cumprida
            
            # Buscar horas agendadas no Quadro de Horários para esta disciplina específica
            agendado_total = db.session.scalar(
                select(func.count(Horario.id))
                .where(Horario.disciplina_id == disciplina.id)
            ) or 0
            
            # O agendado pendente é o que está no quadro mas ainda não foi realizado (lançado no diário)
            agendado_pendente = max(0, agendado_total - realizado)
            
            # Trava de segurança para a soma não ultrapassar o previsto visualmente
            if (realizado + agendado_pendente) > previsto:
                agendado_pendente = previsto - realizado
            
            restante = max(0, previsto - realizado - agendado_pendente)
            
            # Porcentagens para as larguras das barras no CSS
            pct_realizado = (realizado / previsto * 100) if previsto > 0 else 0
            pct_agendado = (agendado_pendente / previsto * 100) if previsto > 0 else 0
            pct_restante = (restante / previsto * 100) if previsto > 0 else 0

            return {
                'previsto': previsto,
                'realizado': realizado,
                'agendado': agendado_pendente,
                'restante': restante,
                'pct_realizado': round(pct_realizado, 1),
                'pct_agendado': round(pct_agendado, 1),
                'pct_restante': round(pct_restante, 1)
            }
        except Exception as e:
            current_app.logger.error(f"Erro ao calcular progresso: {str(e)}")
            return {
                'previsto': 0, 'realizado': 0, 'agendado': 0, 'restante': 0,
                'pct_realizado': 0, 'pct_agendado': 0, 'pct_restante': 0
            }

    @staticmethod
    def get_andamento_total_escola(school_id, ciclo_id=None):
        """
        Calcula o somatório de todas as disciplinas de todas as turmas da escola.
        Utilizado para a tela principal quando nenhuma turma está selecionada.
        """
        try:
            query = select(
                Disciplina.materia,
                func.sum(Disciplina.carga_horaria_prevista).label('total_previsto'),
                func.sum(Disciplina.carga_horaria_cumprida).label('total_cumprido')
            ).where(Disciplina.school_id == school_id)

            if ciclo_id:
                query = query.where(Disciplina.ciclo_id == ciclo_id)
            
            query = query.group_by(Disciplina.materia)
            results = db.session.execute(query).all()
            
            disciplinas_totais = []
            for res in results:
                progresso = DisciplinaService.get_dados_progresso_consolidado(res.materia, school_id)
                
                disciplinas_totais.append({
                    'materia': res.materia,
                    'progresso': progresso
                })
                
            return disciplinas_totais
        except Exception as e:
            current_app.logger.error(f"Erro ao buscar andamento total da escola: {e}")
            return []

    @staticmethod
    def get_dados_progresso_consolidado(materia_nome, school_id):
        """Calcula o progresso somado de uma matéria em todas as turmas da escola."""
        query_data = db.session.execute(
            select(
                func.sum(Disciplina.carga_horaria_prevista),
                func.sum(Disciplina.carga_horaria_cumprida)
            ).where(Disciplina.materia == materia_nome, Disciplina.school_id == school_id)
        ).first()
        
        previsto = query_data[0] or 0
        realizado = query_data[1] or 0
        
        # Soma de tudo que está agendado no Horario para esta matéria em todas as turmas da escola
        agendado_total = db.session.scalar(
            select(func.count(Horario.id))
            .join(Disciplina)
            .where(Disciplina.materia == materia_nome, Disciplina.school_id == school_id)
        ) or 0
        
        agendado_pendente = max(0, agendado_total - realizado)
        if (realizado + agendado_pendente) > previsto:
            agendado_pendente = previsto - realizado
            
        restante = max(0, previsto - realizado - agendado_pendente)
        
        return {
            'previsto': previsto,
            'realizado': realizado,
            'agendado': agendado_pendente,
            'restante': restante,
            'pct_realizado': (realizado / previsto * 100) if previsto > 0 else 0,
            'pct_agendado': (agendado_pendente / previsto * 100) if previsto > 0 else 0,
            'pct_restante': (restante / previsto * 100) if previsto > 0 else 0
        }

    @staticmethod
    def get_dashboard_data(school_id, ciclo_id=None):
        """
        Gera dados de anomalias e alertas para o Dashboard Inteligente.
        """
        try:
            query_turmas = select(Turma).where(Turma.school_id == school_id)
            turmas = db.session.scalars(query_turmas).all()
            turma_ids = [t.id for t in turmas]
            
            if not turma_ids: return None

            query_base = select(Disciplina).where(Disciplina.turma_id.in_(turma_ids))
            if ciclo_id:
                query_base = query_base.where(Disciplina.ciclo_id == ciclo_id)
            
            disciplinas = db.session.scalars(query_base).all()
            if not disciplinas: return None

            total_horas_previstas = sum(d.carga_horaria_prevista for d in disciplinas)
            total_horas_cumpridas = sum(d.carga_horaria_cumprida for d in disciplinas)
            progresso_global = (total_horas_cumpridas / total_horas_previstas * 100) if total_horas_previstas > 0 else 0

            materias_analysis = {}
            for d in disciplinas:
                if d.materia not in materias_analysis:
                    materias_analysis[d.materia] = {'disciplinas': []}
                
                pct = (d.carga_horaria_cumprida / d.carga_horaria_prevista * 100) if d.carga_horaria_prevista > 0 else 0
                
                materias_analysis[d.materia]['disciplinas'].append({
                    'turma': d.turma.nome if d.turma else 'N/D',
                    'pct': pct,
                    'cumprida': d.carga_horaria_cumprida
                })

            materias_risco = []
            
            if progresso_global < 30: tolerance = 25.0
            elif progresso_global < 70: tolerance = 15.0
            else: tolerance = 10.0

            for materia, data in materias_analysis.items():
                lista_pcts = [item['pct'] for item in data['disciplinas']]
                if not lista_pcts: continue
                
                max_pct = max(lista_pcts)
                min_pct = min(lista_pcts)
                amplitude = max_pct - min_pct
                
                if amplitude <= tolerance: continue

                horas_diff = max([i['cumprida'] for i in data['disciplinas']]) - min([i['cumprida'] for i in data['disciplinas']])
                if horas_diff <= 4: continue

                status = 'critical' if amplitude >= (tolerance * 1.5) else 'warning'
                turma_adiantada = next((item['turma'] for item in data['disciplinas'] if item['pct'] == max_pct), '?')
                turma_atrasada = next((item['turma'] for item in data['disciplinas'] if item['pct'] == min_pct), '?')

                materias_risco.append({
                    'materia': materia,
                    'status': status,
                    'amplitude': amplitude,
                    'min_pct': min_pct,
                    'max_pct': max_pct,
                    'turma_min': turma_atrasada,
                    'turma_max': turma_adiantada
                })

            materias_risco.sort(key=lambda x: (0 if x['status'] == 'critical' else 1, -x['amplitude']))

            return {
                'progresso_global': progresso_global,
                'materias_risco': materias_risco,
                'total_analisado': len(materias_analysis)
            }

        except Exception as e:
            current_app.logger.error(f"Erro ao gerar dashboard: {e}")
            return None

    @staticmethod
    def get_disciplinas_by_school(school_id):
        stmt = select(Disciplina).join(Turma).where(Turma.school_id == school_id)
        return db.session.scalars(stmt).all()

    @staticmethod
    def get_disciplina_by_id(id):
        return db.session.get(Disciplina, id)

    @staticmethod
    def create_disciplina(data):
        try:
            nova_disciplina = Disciplina(
                materia=data['materia'],
                carga_horaria_prevista=data['carga_horaria_prevista'],
                carga_horaria_cumprida=data.get('carga_horaria_cumprida', 0),
                turma_id=data['turma_id'],
                ciclo_id=data.get('ciclo_id'),
                school_id=data['school_id']
            )
            db.session.add(nova_disciplina)
            db.session.flush()

            instrutor_id = data.get('instrutor_id')
            instrutor_id_2 = data.get('instrutor_id_2')
            
            if instrutor_id:
                turma = db.session.get(Turma, data['turma_id'])
                novo_vinculo = DisciplinaTurma(
                    disciplina_id=nova_disciplina.id,
                    pelotao=turma.nome,
                    instrutor_id_1=instrutor_id,
                    instrutor_id_2=instrutor_id_2
                )
                db.session.add(novo_vinculo)

            db.session.commit()
            return nova_disciplina, "Disciplina criada com sucesso."
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def update_disciplina(id, data):
        disciplina = db.session.get(Disciplina, id)
        if disciplina:
            disciplina.materia = data.get('materia', disciplina.materia)
            disciplina.carga_horaria_prevista = data.get('carga_horaria_prevista', disciplina.carga_horaria_prevista)
            if 'carga_horaria_cumprida' in data:
                disciplina.carga_horaria_cumprida = data['carga_horaria_cumprida']
            db.session.commit()
            return True, "Atualizado com sucesso."
        return False, "Disciplina não encontrada."

    @staticmethod
    def delete_disciplina(id):
        disciplina = db.session.get(Disciplina, id)
        if disciplina:
            db.session.delete(disciplina)
            db.session.commit()
            return True
        return False