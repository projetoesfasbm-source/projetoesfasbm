# backend/services/disciplina_service.py

from collections import defaultdict
from sqlalchemy import select, func, and_, or_
from sqlalchemy.exc import IntegrityError
from flask import current_app
from datetime import date

from ..models.database import db
from ..models.disciplina import Disciplina
from ..models.disciplina_turma import DisciplinaTurma
from ..models.historico_disciplina import HistoricoDisciplina
from ..models.aluno import Aluno
from ..models.turma import Turma
from ..models.ciclo import Ciclo
from ..models.horario import Horario
from ..models.semana import Semana

class DisciplinaService:
    @staticmethod
    def create_disciplina(data, school_id):
        materia = data.get('materia')
        carga_horaria = data.get('carga_horaria_prevista')
        ciclo_id = data.get('ciclo_id')
        carga_cumprida = data.get('carga_horaria_cumprida', 0)
        turma_ids = data.get('turma_ids', []) # Recebe uma lista de IDs

        if not all([materia, carga_horaria, ciclo_id, turma_ids]):
            return False, 'Matéria, Carga Horária, Ciclo e pelo menos uma Turma são obrigatórios.'

        success_count = 0
        errors = []

        for turma_id in turma_ids:
            try:
                turma = db.session.get(Turma, int(turma_id))
                if not turma or turma.school_id != school_id:
                    errors.append(f'Turma com ID {turma_id} é inválida ou não pertence à sua escola.')
                    continue

                # Verifica se a disciplina já existe para esta turma específica
                if db.session.execute(select(Disciplina).where(Disciplina.materia == materia, Disciplina.turma_id == turma_id)).scalar_one_or_none():
                    errors.append(f'A disciplina "{materia}" já existe na turma {turma.nome}.')
                    continue

                nova_disciplina = Disciplina(
                    materia=materia,
                    carga_horaria_prevista=int(carga_horaria),
                    carga_horaria_cumprida=int(carga_cumprida or 0),
                    ciclo_id=int(ciclo_id),
                    turma_id=int(turma_id)
                )
                db.session.add(nova_disciplina)
                db.session.flush()

                # Associa a disciplina aos alunos da turma selecionada
                for aluno in turma.alunos:
                    matricula = HistoricoDisciplina(aluno_id=aluno.id, disciplina_id=nova_disciplina.id)
                    db.session.add(matricula)
                
                success_count += 1
            except Exception as e:
                db.session.rollback() # Desfaz a transação atual para esta turma
                errors.append(f'Erro ao criar disciplina para a turma ID {turma_id}: {str(e)}')
                # Recomeça a sessão para a próxima iteração
                db.session.begin()

        if success_count > 0:
            db.session.commit()
        
        # Constrói a mensagem final
        message = f'{success_count} disciplina(s) criada(s) com sucesso. '
        if errors:
            message += f"Ocorreram {len(errors)} erro(s): " + "; ".join(errors)
        
        return success_count > 0, message

    @staticmethod
    def update_disciplina(disciplina_id, data):
        disciplina = db.session.get(Disciplina, disciplina_id)
        if not disciplina:
            return False, 'Disciplina não encontrada.'

        try:
            disciplina.materia = data.get('materia', disciplina.materia)
            disciplina.carga_horaria_prevista = int(data.get('carga_horaria_prevista', disciplina.carga_horaria_prevista))
            disciplina.carga_horaria_cumprida = int(data.get('carga_horaria_cumprida', disciplina.carga_horaria_cumprida) or 0)
            disciplina.ciclo_id = int(data.get('ciclo_id', disciplina.ciclo_id))
            # O turma_id não deve ser alterado na edição para manter a integridade.
            db.session.commit()
            return True, 'Disciplina atualizada com sucesso!'
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao atualizar disciplina: {e}")
            return False, 'Ocorreu um erro interno ao atualizar a disciplina.'

    # --- FUNÇÃO ADICIONADA ---
    # Esta função busca todas as disciplinas de UMA escola, corrigindo o vazamento
    # de dados que acontece no Quadro de Horário.
    @staticmethod
    def get_disciplinas_by_school(school_id):
        """
        Busca todas as disciplinas pertencentes a uma escola específica,
        juntando com as turmas para filtrar pelo school_id.
        """
        if not school_id:
            current_app.logger.warn("Tentativa de buscar disciplinas sem um school_id.")
            return []
            
        try:
            return db.session.scalars(
                select(Disciplina)
                .join(Disciplina.turma)
                .where(Turma.school_id == school_id)
                .order_by(Turma.nome, Disciplina.materia)
            ).all()
        except Exception as e:
            current_app.logger.error(f"Erro ao buscar disciplinas por escola: {e}")
            return []
    # --- FIM DA FUNÇÃO ADICIONADA ---

    @staticmethod
    def get_dados_progresso(disciplina, pelotao_nome=None):
        today = date.today()
        today_weekday_index = today.weekday()
        dias_da_semana = ['segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado', 'domingo']
        dias_passados_na_semana = dias_da_semana[:today_weekday_index]

        query = (
            select(func.sum(Horario.duracao))
            .join(Semana)
            .where(
                Horario.disciplina_id == disciplina.id,
                Horario.status == 'confirmado',
                or_(
                    Semana.data_fim < today,
                    and_(
                        Semana.data_inicio <= today,
                        Semana.data_fim >= today,
                        Horario.dia_semana.in_(dias_passados_na_semana)
                    )
                )
            )
        )

        if pelotao_nome:
            query = query.where(Horario.pelotao == pelotao_nome)

        aulas_concluidas = db.session.scalar(query) or 0
        
        total_concluido = aulas_concluidas + disciplina.carga_horaria_cumprida
        carga_horaria_total = disciplina.carga_horaria_prevista
        
        percentual = 0
        if carga_horaria_total > 0:
            percentual = round((total_concluido / carga_horaria_total) * 100)
            
        return {
            'agendado': total_concluido,
            'previsto': carga_horaria_total,
            'percentual': min(percentual, 100)
        }
    
    @staticmethod
    def delete_disciplina(disciplina_id):
        disciplina = db.session.get(Disciplina, disciplina_id)
        if not disciplina:
            return False, 'Disciplina não encontrada.'

        try:
            db.session.delete(disciplina)
            db.session.commit()
            return True, 'Disciplina e todos os seus registros associados foram excluídos com sucesso!'
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao excluir disciplina: {e}")
            return False, 'Ocorreu um erro interno ao excluir a disciplina.'