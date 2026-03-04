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
            
            # Buscar horas agendadas no Quadro de Horários (que ainda não foram cumpridas)
            # Consideramos agendado tudo que está no Horario para esta disciplina
            # mas descontamos o que já foi para o diário (cumprido)
            # Para simplificar e ser visual, buscamos a contagem de registros em Horario
            agendado_total = db.session.scalar(
                select(func.count(Horario.id))
                .where(Horario.disciplina_id == disciplina.id)
            ) or 0
            
            # O que está agendado mas ainda não foi realizado
            # Se o realizado for maior que o agendado (ex: aulas extras não previstas no quadro), 
            # o agendado líquido é 0
            agendado_pendente = max(0, agendado_total - realizado)
            
            # Garantir que a soma não ultrapasse o previsto para a barra não quebrar
            if (realizado + agendado_pendente) > previsto:
                agendado_pendente = previsto - realizado
            
            restante = max(0, previsto - realizado - agendado_pendente)
            
            # Porcentagens para o CSS
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
            return {'previsto': 0, 'realizado': 0, 'agendado': 0, 'restante': 0, 'pct_realizado': 0, 'pct_agendado': 0, 'pct_restante': 0}

    @staticmethod
    def get_andamento_total_escola(school_id, ciclo_id=None):
        """
        Calcula o somatório de todas as disciplinas de todas as turmas para a tela inicial.
        """
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
            # Criamos um objeto temporário para reuso da lógica de progresso
            d_temp = Disciplina(
                materia=res.materia,
                carga_horaria_prevista=res.total_previsto,
                carga_horaria_cumprida=res.total_cumprido
            )
            # Para andamento total, como as turmas podem estar em estágios diferentes,
            # simplificamos o agendado ou buscamos a média.
            progresso = DisciplinaService.get_dados_progresso_consolidado(res.materia, school_id)
            
            disciplinas_totais.append({
                'materia': res.materia,
                'progresso': progresso
            })
            
        return disciplinas_totais

    @staticmethod
    def get_dados_progresso_consolidado(materia_nome, school_id):
        """Versão consolidada para a visão geral da escola"""
        query_data = db.session.execute(
            select(
                func.sum(Disciplina.carga_horaria_prevista),
                func.sum(Disciplina.carga_horaria_cumprida)
            ).where(Disciplina.materia == materia_nome, Disciplina.school_id == school_id)
        ).first()
        
        previsto = query_data[0] or 0
        realizado = query_data[1] or 0
        
        # Agendado total nas turmas para essa matéria
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