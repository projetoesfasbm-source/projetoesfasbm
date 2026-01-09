# backend/services/semana_service.py

from datetime import date
from flask import current_app
from sqlalchemy import select, and_, delete, or_
from ..models.database import db
from ..models.semana import Semana
from ..models.horario import Horario
from ..models.ciclo import Ciclo
from ..models.disciplina import Disciplina
from ..models.disciplina_turma import DisciplinaTurma
from ..models.turma import Turma
from .user_service import UserService

class SemanaService:
    
    @staticmethod
    def get_semana_selecionada(semana_id_str=None, ciclo_id=None):
        active_school_id = UserService.get_current_school_id()
        if not active_school_id:
            return None

        if semana_id_str and str(semana_id_str).isdigit():
            semana = db.session.get(Semana, int(semana_id_str))
            if semana and semana.ciclo and semana.ciclo.school_id == active_school_id:
                return semana

        today = date.today()
        stmt = (
            select(Semana)
            .join(Ciclo)
            .where(Ciclo.school_id == active_school_id)
        )
        
        if ciclo_id:
            stmt = stmt.where(Semana.ciclo_id == ciclo_id)

        semana_atual = db.session.scalars(
            stmt.where(
                Semana.data_inicio <= today,
                Semana.data_fim >= today
            )
        ).first()
        
        if semana_atual:
            return semana_atual

        return db.session.scalars(
            stmt.order_by(Semana.data_inicio.desc())
        ).first()

    @staticmethod
    def add_semana(data: dict):
        nome = data.get('nome')
        data_inicio = data.get('data_inicio')
        data_fim = data.get('data_fim')
        ciclo_id = data.get('ciclo_id')

        if not all([nome, data_inicio, data_fim, ciclo_id]):
            return False, 'Todos os campos, incluindo o ciclo, são obrigatórios.'

        active_school_id = UserService.get_current_school_id()
        ciclo = db.session.get(Ciclo, ciclo_id)
        
        if not ciclo:
            return False, 'Ciclo não encontrado.'
            
        if active_school_id and ciclo.school_id != active_school_id:
            return False, 'Você não pode criar semanas em um ciclo de outra escola.'

        if data_inicio > data_fim:
            return False, 'A data de início não pode ser posterior à data de fim.'

        semana_conflitante = db.session.scalar(
            select(Semana).where(
                Semana.ciclo_id == ciclo_id,
                and_(
                    Semana.data_inicio <= data_fim,
                    Semana.data_fim >= data_inicio
                )
            ).limit(1)
        )

        if semana_conflitante:
            return False, f"Conflito de datas com a semana: '{semana_conflitante.nome}'."

        try:
            nova_semana = Semana(
                nome=nome,
                data_inicio=data_inicio,
                data_fim=data_fim,
                ciclo_id=ciclo_id,
                mostrar_periodo_13=data.get('mostrar_periodo_13', False),
                mostrar_periodo_14=data.get('mostrar_periodo_14', False),
                mostrar_periodo_15=data.get('mostrar_periodo_15', False),
                mostrar_sabado=data.get('mostrar_sabado', False),
                periodos_sabado=int(data.get('periodos_sabado') or 0),
                mostrar_domingo=data.get('mostrar_domingo', False),
                periodos_domingo=int(data.get('periodos_domingo') or 0)
            )
            db.session.add(nova_semana)
            db.session.commit()
            return True, 'Nova semana cadastrada com sucesso!'
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao adicionar semana: {e}")
            return False, f"Erro ao adicionar semana: {str(e)}"

    @staticmethod
    def update_semana(semana_id: int, data: dict):
        semana = db.session.get(Semana, semana_id)
        if not semana: return False, 'Semana não encontrada.'
        
        active_school = UserService.get_current_school_id()
        if active_school and semana.ciclo.school_id != active_school:
            return False, "Permissão negada: Semana pertence a outra escola."

        semana.nome = data.get('nome')
        semana.data_inicio = data.get('data_inicio')
        semana.data_fim = data.get('data_fim')
        
        novo_ciclo_id = data.get('ciclo_id')
        if novo_ciclo_id and int(novo_ciclo_id) != semana.ciclo_id:
             novo_ciclo = db.session.get(Ciclo, novo_ciclo_id)
             if novo_ciclo and novo_ciclo.school_id == active_school:
                 semana.ciclo_id = novo_ciclo_id
             else:
                 return False, "Ciclo de destino inválido ou de outra escola."
        
        semana.mostrar_periodo_13 = 'mostrar_periodo_13' in data
        semana.mostrar_periodo_14 = 'mostrar_periodo_14' in data
        semana.mostrar_periodo_15 = 'mostrar_periodo_15' in data
        
        semana.mostrar_sabado = 'mostrar_sabado' in data
        semana.periodos_sabado = int(data.get('periodos_sabado') or 0)
        
        semana.mostrar_domingo = 'mostrar_domingo' in data
        semana.periodos_domingo = int(data.get('periodos_domingo') or 0)

        try:
            db.session.commit()
            return True, 'Semana atualizada com sucesso.'
        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao atualizar: {str(e)}"

    @staticmethod
    def delete_semana(semana_id: int):
        semana = db.session.get(Semana, semana_id)
        if not semana: return False, 'Semana não encontrada.'
        
        active_school = UserService.get_current_school_id()
        if active_school and semana.ciclo.school_id != active_school:
            return False, "Permissão negada."

        try:
            db.session.query(Horario).filter_by(semana_id=semana_id).delete()
            db.session.delete(semana)
            db.session.commit()
            return True, 'Semana deletada com sucesso.'
        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao deletar: {str(e)}"

    @staticmethod
    def deletar_ciclo(ciclo_id):
        """
        Deleta um ciclo e TODAS as suas dependências via SQL Direto para garantir Cascata.
        """
        ciclo = db.session.get(Ciclo, ciclo_id)
        if not ciclo:
            return False, "Ciclo não encontrado."

        active_school_id = UserService.get_current_school_id()
        if active_school_id and ciclo.school_id != active_school_id:
             return False, "Permissão negada para excluir este ciclo."

        try:
            # Subqueries para identificar o que apagar
            sub_semanas = select(Semana.id).where(Semana.ciclo_id == ciclo_id)
            sub_disciplinas = select(Disciplina.id).where(Disciplina.ciclo_id == ciclo_id)

            # 1. Apagar Horários (dependem de Semana ou Disciplina)
            db.session.execute(delete(Horario).where(
                or_(
                    Horario.semana_id.in_(sub_semanas),
                    Horario.disciplina_id.in_(sub_disciplinas)
                )
            ))

            # 2. Apagar Vínculos de Turma/Instrutor (dependem de Disciplina)
            db.session.execute(delete(DisciplinaTurma).where(
                DisciplinaTurma.disciplina_id.in_(sub_disciplinas)
            ))

            # 3. Apagar Semanas (dependem de Ciclo)
            db.session.execute(delete(Semana).where(Semana.ciclo_id == ciclo_id))

            # 4. Apagar Disciplinas (dependem de Ciclo)
            db.session.execute(delete(Disciplina).where(Disciplina.ciclo_id == ciclo_id))

            # 5. Apagar Turmas (Se houver vinculo direto com Ciclo)
            if hasattr(Turma, 'ciclo_id'):
                db.session.execute(delete(Turma).where(Turma.ciclo_id == ciclo_id))

            # 6. Apagar o Ciclo
            db.session.execute(delete(Ciclo).where(Ciclo.id == ciclo_id))
            
            # Limpa sessão para evitar inconsistências
            db.session.expire_all()
            
            db.session.commit()
            return True, "Ciclo e todos os dados associados foram excluídos com sucesso."
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao excluir ciclo: {str(e)}")
            return False, f"Erro ao excluir ciclo: {str(e)}"