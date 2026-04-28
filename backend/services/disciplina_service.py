# backend/services/disciplina_service.py

from flask import current_app
from sqlalchemy import select, func, distinct, case, or_, and_
from datetime import datetime, timedelta
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
        Calcula o progresso real e agendado de uma disciplina cruzando dados do Quadro de Horário.
        """
        try:
            previsto = disciplina.carga_horaria_prevista or 0
            hoje = datetime.now().date()
            
            agendamentos = db.session.scalars(
                select(Horario)
                .join(Semana, Horario.semana_id == Semana.id)
                .where(Horario.disciplina_id == disciplina.id)
            ).all()

            mapa_dias = {
                'segunda': 0, 'segunda-feira': 0, 'terça': 1, 'terca': 1, 'terça-feira': 1,
                'quarta': 2, 'quarta-feira': 2, 'quinta': 3, 'quinta-feira': 3,
                'sexta': 4, 'sexta-feira': 4, 'sábado': 5, 'sabado': 5, 'domingo': 6
            }

            ministradas = 0
            agendadas_futuro = 0

            for ag in agendamentos:
                qtd = ag.duracao if ag.duracao else 1
                data_real = ag.semana.data_inicio
                dia_text = ag.dia_semana.lower().strip() if ag.dia_semana else ""
                offset = mapa_dias.get(dia_text)
                
                if offset is not None:
                    data_real = ag.semana.data_inicio + timedelta(days=offset)
                
                data_comp = data_real.date() if isinstance(data_real, datetime) else data_real

                if data_comp <= hoje:
                    ministradas += qtd
                else:
                    agendadas_futuro += qtd

            realizado_total = max(ministradas, disciplina.carga_horaria_cumprida or 0)
            if realizado_total > previsto and previsto > 0:
                realizado_total = previsto
            
            restante = max(0, previsto - realizado_total - agendadas_futuro)
            
            return {
                'previsto': previsto,
                'realizado': realizado_total,
                'pct_realizado': round((realizado_total / previsto * 100), 1) if previsto > 0 else 0,
                'agendado': agendadas_futuro,
                'pct_agendado': round((agendadas_futuro / previsto * 100), 1) if previsto > 0 else 0,
                'restante_para_planejar': restante
            }
        except Exception as e:
            current_app.logger.error(f"Erro no cálculo de progresso: {e}")
            return {'previsto': 0, 'realizado': 0, 'pct_realizado': 0, 'agendado': 0, 'pct_agendado': 0, 'restante_para_planejar': 0}

    @staticmethod
    def get_dashboard_data(school_id, ciclo_id=None):
        """
        Gera o Painel de Alertas detectando assincronia entre turmas da mesma escola.
        """
        try:
            # Busca turmas APENAS da escola atual
            query_turmas = select(Turma).where(Turma.school_id == school_id)
            turmas = db.session.scalars(query_turmas).all()
            turma_ids = [t.id for t in turmas]
            total_turmas = len(turma_ids) # CONTAGEM REAL DE TURMAS (Ex: 10 em Montenegro)
            
            if not turma_ids: return None

            query_base = select(Disciplina).where(Disciplina.turma_id.in_(turma_ids))
            if ciclo_id:
                query_base = query_base.where(Disciplina.ciclo_id == ciclo_id)
            
            disciplinas = db.session.scalars(query_base).all()
            if not disciplinas: return None

            materias_analysis = {}
            total_previsto_global = 0
            total_realizado_global = 0

            for d in disciplinas:
                prog = DisciplinaService.get_dados_progresso(d)
                
                if d.materia not in materias_analysis:
                    materias_analysis[d.materia] = {'disciplinas': []}
                
                total_previsto_global += prog['previsto']
                total_realizado_global += prog['realizado']

                materias_analysis[d.materia]['disciplinas'].append({
                    'turma': d.turma.nome if d.turma else 'N/D',
                    'pct': prog['pct_realizado'],
                    'cumprida': prog['realizado'],
                    'id': d.id
                })

            progresso_global = (total_realizado_global / total_previsto_global * 100) if total_previsto_global > 0 else 0

            materias_risco = []
            if progresso_global < 30: tolerance = 20.0
            elif progresso_global < 70: tolerance = 12.0
            else: tolerance = 8.0

            for materia, data in materias_analysis.items():
                lista_pcts = [item['pct'] for item in data['disciplinas']]
                if not lista_pcts or len(lista_pcts) < 2: continue
                
                max_pct = max(lista_pcts)
                min_pct = min(lista_pcts)
                amplitude = max_pct - min_pct
                
                if amplitude > tolerance:
                    status = 'critical' if amplitude >= (tolerance * 1.8) else 'warning'
                    t_min = next(item for item in data['disciplinas'] if item['pct'] == min_pct)
                    t_max = next(item for item in data['disciplinas'] if item['pct'] == max_pct)

                    materias_risco.append({
                        'materia': materia,
                        'status': status,
                        'amplitude': amplitude,
                        'min_pct': min_pct,
                        'max_pct': max_pct,
                        'turma_min': t_min['turma'],
                        'turma_max': t_max['turma'],
                        'disciplina_id_min': t_min['id']
                    })

            materias_risco.sort(key=lambda x: (0 if x['status'] == 'critical' else 1, -x['amplitude']))

            return {
                'progresso_global': progresso_global,
                'materias_risco': materias_risco,
                'total_analisado': len(materias_analysis), # Matérias únicas (Ex: 29)
                'total_turmas': total_turmas # Turmas da escola (Ex: 10)
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