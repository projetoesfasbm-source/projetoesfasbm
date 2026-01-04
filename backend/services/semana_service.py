# backend/services/semana_service.py

from datetime import date
from flask import current_app
from sqlalchemy import select, and_
from sqlalchemy.orm import joinedload

from ..models.database import db
from ..models.semana import Semana
from ..models.horario import Horario
from ..models.ciclo import Ciclo
from .user_service import UserService

class SemanaService:
    
    @staticmethod
    def get_semanas_by_school():
        """
        Retorna todas as semanas vinculadas a ciclos da escola ativa.
        Filtra pelo school_id do Ciclo para evitar vazamento entre escolas.
        """
        active_school_id = UserService.get_current_school_id()
        if not active_school_id:
            return []
            
        stmt = (
            select(Semana)
            .join(Ciclo, Semana.ciclo_id == Ciclo.id)
            .where(Ciclo.school_id == active_school_id)
            .order_by(Semana.data_inicio.desc())
        )
        return db.session.scalars(stmt).all()

    @staticmethod
    def get_semana_selecionada(semana_id_str=None, ciclo_id=None):
        """
        Busca uma semana específica ou a atual, GARANTINDO que pertença à escola.
        """
        active_school_id = UserService.get_current_school_id()
        if not active_school_id:
            return None

        # 1. Busca por ID (se fornecido)
        if semana_id_str and str(semana_id_str).isdigit():
            semana = db.session.get(Semana, int(semana_id_str))
            
            # BLINDAGEM: A semana pertence a um ciclo desta escola?
            if semana and semana.ciclo and semana.ciclo.school_id == active_school_id:
                return semana
            # Se a semana existe mas é de outra escola, ignoramos (retorna None)

        # 2. Busca Automática (Semana Atual ou Última) dentro do ciclo/escola
        today = date.today()
        
        stmt = (
            select(Semana)
            .join(Ciclo, Semana.ciclo_id == Ciclo.id)
            .where(Ciclo.school_id == active_school_id)
        )
        
        if ciclo_id:
            stmt = stmt.where(Semana.ciclo_id == ciclo_id)

        # Tenta achar a semana que engloba "hoje"
        semana_atual = db.session.scalars(
            stmt.where(
                Semana.data_inicio <= today,
                Semana.data_fim >= today
            )
        ).first()
        
        if semana_atual:
            return semana_atual

        # Se não houver semana hoje, retorna a última cadastrada da escola/ciclo
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

        # --- NOVA VERIFICAÇÃO DE SEGURANÇA ---
        active_school_id = UserService.get_current_school_id()
        ciclo = db.session.get(Ciclo, ciclo_id)
        if not ciclo or (active_school_id and ciclo.school_id != active_school_id):
            return False, 'O Ciclo selecionado não pertence à sua escola.'
        # -------------------------------------

        if data_inicio > data_fim:
            return False, 'A data de início não pode ser posterior à data de fim.'

        # Verifica conflito apenas dentro do mesmo ciclo
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
        
        # Proteção: Só edita se for da escola ativa
        active_school = UserService.get_current_school_id()
        if active_school and semana.ciclo.school_id != active_school:
            return False, "Permissão negada: Semana pertence a outra escola."

        semana.nome = data.get('nome')
        semana.data_inicio = data.get('data_inicio')
        semana.data_fim = data.get('data_fim')
        # Atualiza o ciclo se fornecido, validando a escola
        new_ciclo_id = data.get('ciclo_id')
        if new_ciclo_id and int(new_ciclo_id) != semana.ciclo_id:
             new_ciclo = db.session.get(Ciclo, new_ciclo_id)
             if new_ciclo and new_ciclo.school_id == active_school:
                 semana.ciclo_id = new_ciclo_id
        
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
        
        # Proteção: Só deleta se for da escola ativa
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