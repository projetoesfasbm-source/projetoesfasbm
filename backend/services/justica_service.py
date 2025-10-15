# backend/services/justica_service.py

from ..models.database import db
from ..models.processo_disciplina import ProcessoDisciplina
from ..models.aluno import Aluno
from ..models.user import User
from ..models.turma import Turma
from ..models.historico import HistoricoAluno
from sqlalchemy import select, or_, and_, func
from sqlalchemy.orm import joinedload
from datetime import datetime, timezone
from flask import current_app
from collections import Counter

class JusticaService:
    @staticmethod
    def get_analise_disciplinar_data():
        """
        Coleta e processa dados de todos os processos disciplinares para análise.
        """
        processos = db.session.scalars(
            select(ProcessoDisciplina)
            .options(
                joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.turma),
                joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user)
            )
        ).all()

        # 1. Contagens gerais
        total_processos = len(processos)
        status_counts = Counter(p.status for p in processos)

        # 2. Contagem por turma
        turma_counts = Counter()
        for p in processos:
            if p.aluno and p.aluno.turma:
                turma_counts[p.aluno.turma.nome] += 1

        # 3. Contagem por mês
        month_counts = Counter()
        for p in processos:
            mes_ano = p.data_ocorrencia.strftime("%Y-%m") # Formato AAAA-MM para ordenação
            month_counts[mes_ano] += 1
        
        # Ordena os meses para o gráfico de linha
        sorted_months = sorted(month_counts.keys())
        # Formata os meses para exibição (ex: "Out/2025")
        month_labels = [datetime.strptime(m, "%Y-%m").strftime("%b/%Y") for m in sorted_months]
        month_data = [month_counts[m] for m in sorted_months]

        # 4. Fatos mais comuns (Top 5)
        fato_counts = Counter(p.fato_constatado.strip() for p in processos)
        top_5_fatos = fato_counts.most_common(5)

        return {
            'total_processos': total_processos,
            'status_counts': dict(status_counts),
            'turma_labels': list(turma_counts.keys()),
            'turma_data': list(turma_counts.values()),
            'month_labels': month_labels,
            'month_data': month_data,
            'top_fatos_labels': [fato[0] for fato in top_5_fatos],
            'top_fatos_data': [fato[1] for fato in top_5_fatos],
        }

    @staticmethod
    def get_processos_para_usuario(user):
        """Busca processos para um usuário específico (aluno ou admin)."""
        stmt = select(ProcessoDisciplina)
        if user.role == 'aluno' and hasattr(user, 'aluno_profile') and user.aluno_profile:
            stmt = stmt.where(ProcessoDisciplina.aluno_id == user.aluno_profile.id)
            
        return db.session.scalars(stmt.options(
            joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user),
            joinedload(ProcessoDisciplina.relator)
        ).order_by(ProcessoDisciplina.data_ocorrencia.desc())).all()

    @staticmethod
    def get_finalized_processos():
        """Busca apenas os processos que estão verdadeiramente finalizados."""
        stmt = select(ProcessoDisciplina).where(
            ProcessoDisciplina.status == 'Finalizado',
            ProcessoDisciplina.decisao_final.isnot(None)
        )
        return db.session.scalars(stmt.options(
            joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user),
            joinedload(ProcessoDisciplina.relator)
        ).order_by(ProcessoDisciplina.data_decisao.desc())).all()

    @staticmethod
    def get_processos_por_ids(processo_ids):
        """Busca uma lista de processos a partir de seus IDs."""
        if not processo_ids:
            return []
        
        stmt = select(ProcessoDisciplina).where(ProcessoDisciplina.id.in_(processo_ids))
        return db.session.scalars(stmt.options(
            joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user),
            joinedload(ProcessoDisciplina.relator)
        )).all()

    @staticmethod
    def criar_processo(fato, observacao, aluno_id, relator_id):
        """Cria um novo processo disciplinar e um registro no histórico do aluno."""
        try:
            aluno = db.session.get(Aluno, aluno_id)
            if not aluno:
                return False, "Aluno não encontrado."

            novo_processo = ProcessoDisciplina(
                fato_constatado=fato,
                observacao=observacao,
                aluno_id=aluno_id,
                relator_id=relator_id
            )
            db.session.add(novo_processo)

            novo_historico = HistoricoAluno(
                aluno_id=aluno_id,
                tipo='Processo Disciplinar',
                descricao=f'Abertura de processo: {fato}',
                data_inicio=datetime.now(timezone.utc)
            )
            db.session.add(novo_historico)
            
            db.session.commit()
            return True, "Transgressão registrada com sucesso e adicionada ao histórico do aluno!"
        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao registrar transgressão: {e}"

    @staticmethod
    def registrar_ciente(processo_id, user):
        """Registra que o aluno deu ciência do processo."""
        processo = db.session.get(ProcessoDisciplina, processo_id)
        if not processo or (hasattr(user, 'aluno_profile') and processo.aluno_id != user.aluno_profile.id):
            return False, "Processo não encontrado ou não pertence a você."
        
        processo.status = 'Aluno Notificado'
        processo.data_ciente = datetime.now(timezone.utc)
        db.session.commit()
        return True, "Ciência registrada com sucesso."

    @staticmethod
    def enviar_defesa(processo_id, defesa, user):
        """Salva a defesa do aluno para um processo."""
        processo = db.session.get(ProcessoDisciplina, processo_id)
        if not processo or (hasattr(user, 'aluno_profile') and processo.aluno_id != user.aluno_profile.id):
            return False, "Processo não encontrado ou não pertence a você."
            
        processo.status = 'Defesa Enviada'
        processo.defesa = defesa
        processo.data_defesa = datetime.now(timezone.utc)
        db.session.commit()
        return True, "Defesa enviada com sucesso."

    @staticmethod
    def finalizar_processo(processo_id, justificacao, fundamentacao):
        """Finaliza um processo com base na justificação e fundamentação."""
        processo = db.session.get(ProcessoDisciplina, processo_id)
        if not processo:
            return False, "Processo não encontrado."

        historico_correspondente = db.session.scalars(select(HistoricoAluno).where(
            HistoricoAluno.aluno_id == processo.aluno_id,
            HistoricoAluno.descricao.like(f"%Abertura de processo: {processo.fato_constatado}%"),
            HistoricoAluno.data_fim.is_(None)
        ).order_by(HistoricoAluno.data_inicio.desc())).first()
        
        if historico_correspondente:
            historico_correspondente.data_fim = datetime.now(timezone.utc)
            
        processo.status = 'Finalizado'
        processo.fundamentacao = fundamentacao
        processo.data_decisao = datetime.now(timezone.utc)

        if justificacao == 'Justificado':
            processo.decisao_final = 'Justificado'
        else: # Não Justificado
            processo.decisao_final = 'Sustação da Dispensa'
        
        db.session.commit()
        return True, "Processo finalizado com sucesso."

    @staticmethod
    def deletar_processo(processo_id):
        """Exclui um processo disciplinar e o registro de histórico associado."""
        processo = db.session.get(ProcessoDisciplina, processo_id)
        if not processo:
            return False, "Processo não encontrado."
        
        try:
            historico_para_deletar = db.session.scalars(select(HistoricoAluno).where(
                HistoricoAluno.aluno_id == processo.aluno_id,
                HistoricoAluno.descricao.like(f"%Abertura de processo: {processo.fato_constatado}%")
            )).first()

            if historico_para_deletar:
                db.session.delete(historico_para_deletar)

            db.session.delete(processo)
            db.session.commit()
            return True, "Processo disciplinar e seu registro no histórico foram excluídos com sucesso."
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao deletar processo: {e}")
            return False, "Ocorreu um erro ao tentar excluir o processo."