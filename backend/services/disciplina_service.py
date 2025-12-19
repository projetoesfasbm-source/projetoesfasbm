# backend/services/disciplina_service.py

from collections import defaultdict
from sqlalchemy import select, func, and_, or_
from sqlalchemy.exc import IntegrityError
from flask import current_app
from datetime import date, timedelta

from ..models.database import db
from ..models.disciplina import Disciplina
from ..models.disciplina_turma import DisciplinaTurma
from ..models.historico_disciplina import HistoricoDisciplina
from ..models.aluno import Aluno
from ..models.turma import Turma
from ..models.ciclo import Ciclo
from ..models.horario import Horario
from ..models.semana import Semana
from ..models.diario_classe import DiarioClasse

class DisciplinaService:
    
    @staticmethod
    def get_all_disciplinas():
        """Retorna todas as disciplinas ordenadas por nome."""
        return db.session.scalars(select(Disciplina).order_by(Disciplina.materia)).all()

    @staticmethod
    def get_disciplina_by_id(disciplina_id):
        """Busca uma disciplina pelo ID."""
        return db.session.get(Disciplina, disciplina_id)

    @staticmethod
    def get_disciplinas_by_turma(turma_id):
        """Retorna disciplinas de uma turma específica."""
        return db.session.scalars(
            select(Disciplina)
            .where(Disciplina.turma_id == turma_id)
            .order_by(Disciplina.materia)
        ).all()

    @staticmethod
    def get_disciplinas_by_school(school_id):
        """Retorna disciplinas vinculadas a uma escola."""
        if not school_id:
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

    @staticmethod
    def create_disciplina(data, school_id):
        """
        Cria novas disciplinas para as turmas selecionadas.
        """
        materia = data.get('materia')
        carga_horaria = data.get('carga_horaria_prevista')
        ciclo_id = data.get('ciclo_id')
        carga_cumprida = data.get('carga_horaria_cumprida', 0)
        turma_ids = data.get('turma_ids', [])

        if not all([materia, carga_horaria, ciclo_id, turma_ids]):
            return False, 'Dados incompletos. Verifique Matéria, Carga Horária, Ciclo e Turmas.'

        success_count = 0
        
        for turma_id in turma_ids:
            try:
                turma = db.session.get(Turma, int(turma_id))
                if not turma or turma.school_id != school_id:
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
                
                # Vincula alunos
                for aluno in turma.alunos:
                    historico = HistoricoDisciplina(
                        aluno_id=aluno.id,
                        disciplina_id=nova_disciplina.id
                    )
                    db.session.add(historico)
                
                success_count += 1
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Erro ao criar disciplina para turma {turma_id}: {e}")
                db.session.begin()
        
        if success_count > 0:
            db.session.commit()
            return True, f'{success_count} disciplinas criadas com sucesso.'
        else:
            return False, 'Nenhuma disciplina foi criada.'

    @staticmethod
    def update_disciplina(disciplina_id, data):
        """Atualiza os dados de uma disciplina existente."""
        disciplina = db.session.get(Disciplina, disciplina_id)
        if not disciplina:
            return False, 'Disciplina não encontrada.'
            
        try:
            if 'materia' in data:
                disciplina.materia = data.get('materia')
            
            if 'carga_horaria_prevista' in data:
                disciplina.carga_horaria_prevista = int(data.get('carga_horaria_prevista'))
                
            if 'carga_horaria_cumprida' in data:
                val = data.get('carga_horaria_cumprida')
                disciplina.carga_horaria_cumprida = int(val) if val else 0
                
            if 'ciclo_id' in data:
                disciplina.ciclo_id = int(data.get('ciclo_id'))
                
            db.session.commit()
            return True, 'Disciplina atualizada com sucesso.'
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao atualizar disciplina {disciplina_id}: {e}")
            return False, 'Erro ao atualizar disciplina.'

    @staticmethod
    def delete_disciplina(disciplina_id):
        """Remove uma disciplina e seus vínculos."""
        disciplina = db.session.get(Disciplina, disciplina_id)
        if not disciplina:
            return False, 'Disciplina não encontrada.'
            
        try:
            db.session.delete(disciplina)
            db.session.commit()
            return True, 'Disciplina removida com sucesso.'
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao deletar disciplina {disciplina_id}: {e}")
            return False, 'Erro ao remover disciplina. Verifique dependências.'

    @staticmethod
    def get_dados_progresso(disciplina, pelotao_nome=None):
        """
        Calcula o progresso da disciplina (Carga Horária Cumprida vs Prevista).
        
        IMPORTANTE: A consulta soma apenas a coluna 'duracao' da tabela Horario,
        sem fazer JOIN com Instrutor, evitando duplicação de horas.
        """
        today = date.today()
        
        # Query otimizada: Soma direta na tabela Horario
        query = (
            select(func.sum(Horario.duracao))
            .join(Semana)
            .where(
                Horario.disciplina_id == disciplina.id,
                Horario.status == 'confirmado',
                Semana.data_inicio <= today
            )
        )

        if pelotao_nome:
            query = query.where(Horario.pelotao == pelotao_nome)

        aulas_concluidas = db.session.scalar(query) or 0
        
        # Soma total
        total_concluido = float(aulas_concluidas) + float(disciplina.carga_horaria_cumprida or 0)
        carga_horaria_total = float(disciplina.carga_horaria_prevista or 0)
        
        percentual = 0
        if carga_horaria_total > 0:
            percentual = round((total_concluido / carga_horaria_total) * 100)
            
        return {
            'agendado': total_concluido,
            'previsto': carga_horaria_total,
            'percentual': min(percentual, 100)
        }

    @staticmethod
    def sincronizar_progresso_aulas(school_id=None):
        """
        Recalcula e persiste a carga horária cumprida de todas as disciplinas.
        """
        try:
            query = select(Disciplina)
            if school_id:
                query = query.join(Turma).where(Turma.school_id == school_id)
            
            disciplinas = db.session.scalars(query).all()
            updates_count = 0
            
            for disciplina in disciplinas:
                # Recalcula do zero usando lógica segura
                novo_total = db.session.query(func.sum(Horario.duracao))\
                    .join(Semana)\
                    .filter(
                        Horario.disciplina_id == disciplina.id,
                        Horario.status == 'confirmado',
                        Semana.data_fim < date.today()
                    ).scalar() or 0
                
                # Atualiza apenas se diferente
                if float(disciplina.carga_horaria_cumprida or 0) != float(novo_total):
                    disciplina.carga_horaria_cumprida = novo_total
                    db.session.add(disciplina)
                    updates_count += 1
            
            db.session.commit()
            return True, f"{updates_count} disciplinas sincronizadas."
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro na sincronização de progresso: {e}")
            return False, str(e)