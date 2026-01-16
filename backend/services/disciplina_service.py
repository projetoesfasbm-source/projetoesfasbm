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
        Calcula o progresso de uma disciplina específica.
        Usado pela lista principal (Visualização Legada/Detalhada).
        """
        try:
            previsto = disciplina.carga_horaria_prevista
            realizado = disciplina.carga_horaria_cumprida
            pct_realizado = int((realizado / previsto * 100)) if previsto > 0 else 0
            
            # Cálculo simples para visualização rápida
            # Se precisar de "agendado futuro" preciso, seria necessário query pesada no Horario
            # Por enquanto, mantemos 0 ou lógica simplificada para não travar a lista
            agendado = 0 
            pct_agendado = 0
            restante = previsto - realizado
            
            return {
                'previsto': previsto,
                'realizado': realizado,
                'pct_realizado': pct_realizado,
                'agendado': agendado,
                'pct_agendado': pct_agendado,
                'restante_para_planejar': restante
            }
        except Exception:
            return {
                'previsto': 0, 'realizado': 0, 'pct_realizado': 0,
                'agendado': 0, 'pct_agendado': 0, 'restante_para_planejar': 0
            }

    @staticmethod
    def get_dashboard_data(school_id, ciclo_id=None):
        """
        Gera dados APENAS de anomalias e alertas para o Dashboard Inteligente.
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
                carga_horaria_cumprida=0,
                turma_id=data['turma_id'],
                ciclo_id=data['ciclo_id']
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