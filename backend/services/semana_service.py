# backend/services/semana_service.py

from ..models.database import db
from ..models.semana import Semana
from ..models.horario import Horario
from sqlalchemy import select, and_
from datetime import datetime
from flask import current_app

class SemanaService:
    @staticmethod
    def add_semana(data: dict):
        """Cria uma nova semana a partir dos dados de um formulário, com validação de sobreposição."""
        nome = data.get('nome')
        data_inicio = data.get('data_inicio')
        data_fim = data.get('data_fim')
        ciclo_id = data.get('ciclo_id')

        if not all([nome, data_inicio, data_fim, ciclo_id]):
            return False, 'Todos os campos, incluindo o ciclo, são obrigatórios.'

        # --- NOVA VALIDAÇÃO 1: Garante que a data de início não é posterior à de fim ---
        if data_inicio > data_fim:
            return False, 'A data de início não pode ser posterior à data de fim.'

        # --- NOVA VALIDAÇÃO 2: Verifica se há semanas com datas sobrepostas no mesmo ciclo ---
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
            return False, f"As datas fornecidas entram em conflito com uma semana existente: '{semana_conflitante.nome}' (de {semana_conflitante.data_inicio.strftime('%d/%m/%Y')} a {semana_conflitante.data_fim.strftime('%d/%m/%Y')})."

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
    def delete_semana(semana_id: int):
        """Exclui uma semana e todas as aulas agendadas associadas a ela."""
        semana = db.session.get(Semana, semana_id)
        if not semana:
            return False, 'Semana não encontrada.'

        try:
            # --- LÓGICA DE EXCLUSÃO ALTERADA ---
            # Primeiro, deleta todas as aulas (horarios) associadas a esta semana.
            aulas_deletadas = db.session.query(Horario).filter_by(semana_id=semana_id).delete()
            
            # Em seguida, deleta a semana.
            db.session.delete(semana)
            db.session.commit()
            
            mensagem = 'Semana deletada com sucesso.'
            if aulas_deletadas > 0:
                mensagem = f'Semana e suas {aulas_deletadas} aulas agendadas foram deletadas com sucesso.'
                
            return True, mensagem
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao deletar semana: {e}")
            return False, f"Erro ao deletar semana: {str(e)}"