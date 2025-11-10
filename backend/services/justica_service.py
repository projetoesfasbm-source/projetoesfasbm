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
from flask import current_app, url_for
from collections import Counter
from .notification_service import NotificationService
from .email_service import EmailService

class JusticaService:
    @staticmethod
    def get_analise_disciplinar_data():
        processos = db.session.scalars(
            select(ProcessoDisciplina)
            .options(
                joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.turma),
                joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user)
            )
        ).all()

        total_processos = len(processos)
        status_counts = Counter(p.status for p in processos)
        turma_counts = Counter()
        for p in processos:
            if p.aluno and p.aluno.turma:
                turma_counts[p.aluno.turma.nome] += 1
        month_counts = Counter()
        for p in processos:
            mes_ano = p.data_ocorrencia.strftime("%Y-%m")
            month_counts[mes_ano] += 1
        sorted_months = sorted(month_counts.keys())
        month_labels = [datetime.strptime(m, "%Y-%m").strftime("%b/%Y") for m in sorted_months]
        month_data = [month_counts[m] for m in sorted_months]
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
        stmt = select(ProcessoDisciplina)
        if user.role == 'aluno' and hasattr(user, 'aluno_profile') and user.aluno_profile:
            stmt = stmt.where(ProcessoDisciplina.aluno_id == user.aluno_profile.id)
            
        return db.session.scalars(stmt.options(
            joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user),
            joinedload(ProcessoDisciplina.relator)
        ).order_by(ProcessoDisciplina.data_ocorrencia.desc())).all()

    @staticmethod
    def get_finalized_processos():
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
        if not processo_ids:
            return []
        
        stmt = select(ProcessoDisciplina).where(ProcessoDisciplina.id.in_(processo_ids))
        return db.session.scalars(stmt.options(
            joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user),
            joinedload(ProcessoDisciplina.relator)
        )).all()

    @staticmethod
    def criar_processo(fato, observacao, aluno_id, relator_id):
        """Cria um novo processo disciplinar e notifica o aluno por Push e E-mail."""
        try:
            aluno = db.session.get(Aluno, aluno_id)
            if not aluno or not aluno.user:
                return False, "Aluno ou perfil de usuário do aluno não encontrado."

            novo_processo = ProcessoDisciplina(
                fato_constatado=fato,
                observacao=observacao,
                aluno_id=aluno_id,
                relator_id=relator_id
            )
            db.session.add(novo_processo)

            novo_historico = HistoricoAluno(
                aluno_id=aluno_id,
                tipo='Infração Disciplinar',
                descricao=f'Abertura de processo: {fato}',
                data_inicio=datetime.now(timezone.utc)
            )
            db.session.add(novo_historico)
            
            db.session.flush() # Garante o ID do processo
            
            # --- NOTIFICAÇÕES (INÍCIO) ---
            message = "Um novo processo disciplinar foi aberto em seu nome. Por favor, acesse o sistema para dar ciência."
            notification_url = url_for('justica.index', _external=True)
            
            # 1. App/Push
            NotificationService.create_notification(aluno.user.id, message, notification_url)
            # 2. E-mail
            if aluno.user.email:
                EmailService.send_justice_notification_email(aluno.user, novo_processo, notification_url)
            # --- NOTIFICAÇÕES (FIM) ---
            
            db.session.commit()
            return True, "Infração registrada com sucesso e aluno notificado!"
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao criar processo: {e}")
            return False, f"Erro ao registrar infração: {e}"

    @staticmethod
    def registrar_ciente(processo_id, user):
        """Registra a ciência e notifica os administradores."""
        processo = db.session.get(ProcessoDisciplina, processo_id)
        if not processo or (hasattr(user, 'aluno_profile') and processo.aluno_id != user.aluno_profile.id):
            return False, "Processo não encontrado ou não pertence a você."
        
        processo.status = 'Aluno Notificado'
        processo.data_ciente = datetime.now(timezone.utc)

        turma = processo.aluno.turma
        if turma and turma.school_id:
            message = f"O aluno {user.nome_de_guerra} deu ciência do processo disciplinar #{processo.id}."
            notification_url = url_for('justica.index', _external=True)
            NotificationService.create_notification_for_roles(turma.school_id, ['admin_escola', 'super_admin', 'programador'], message, notification_url)
        
        db.session.commit()
        return True, "Ciência registrada com sucesso."

    @staticmethod
    def enviar_defesa(processo_id, defesa, user):
        """Salva a defesa e notifica os administradores."""
        processo = db.session.get(ProcessoDisciplina, processo_id)
        if not processo or (hasattr(user, 'aluno_profile') and processo.aluno_id != user.aluno_profile.id):
            return False, "Processo não encontrado ou não pertence a você."
            
        processo.status = 'Defesa Enviada'
        processo.defesa = defesa
        processo.data_defesa = datetime.now(timezone.utc)

        turma = processo.aluno.turma
        if turma and turma.school_id:
            message = f"O aluno {user.nome_de_guerra} enviou a defesa para o processo #{processo.id}."
            notification_url = url_for('justica.index', _external=True)
            NotificationService.create_notification_for_roles(turma.school_id, ['admin_escola', 'super_admin', 'programador'], message, notification_url)

        db.session.commit()
        return True, "Defesa enviada com sucesso."

    @staticmethod
    def finalizar_processo(processo_id, decisao, fundamentacao, detalhes_sancao):
        """Finaliza o processo, registra no histórico e notifica o aluno do veredito por e-mail."""
        processo = db.session.get(ProcessoDisciplina, processo_id)
        if not processo:
            return False, "Processo não encontrado."

        # Busca histórico para fechar
        historico_correspondente = db.session.scalars(select(HistoricoAluno).where(
            HistoricoAluno.aluno_id == processo.aluno_id,
            HistoricoAluno.descricao.like(f"%Abertura de processo: {processo.fato_constatado[:50]}%"),
            HistoricoAluno.data_fim.is_(None)
        ).order_by(HistoricoAluno.data_inicio.desc())).first()
        
        if historico_correspondente:
            historico_correspondente.data_fim = datetime.now(timezone.utc)
            
        processo.status = 'Finalizado'
        processo.fundamentacao = fundamentacao
        processo.data_decisao = datetime.now(timezone.utc)
        processo.decisao_final = decisao
        processo.detalhes_sancao = detalhes_sancao if detalhes_sancao else None

        db.session.commit()

        # --- NOTIFICAÇÃO DE VEREDITO (INÍCIO) ---
        # Recarrega o aluno com o user para garantir que temos o e-mail
        if processo.aluno and processo.aluno.user and processo.aluno.user.email:
             # Notificação Push
             message = f"O processo disciplinar #{processo.id} foi finalizado. Veredito: {decisao}."
             # URL leva para o histórico ou para a lista de processos (ajuste conforme necessidade)
             notification_url = url_for('justica.index', _external=True) 
             NotificationService.create_notification(processo.aluno.user.id, message, notification_url)

             # Notificação por E-mail
             EmailService.send_justice_verdict_email(processo.aluno.user, processo)
        # --- NOTIFICAÇÃO DE VEREDITO (FIM) ---

        return True, "Processo finalizado com sucesso e aluno notificado do veredito."

    @staticmethod
    def deletar_processo(processo_id):
        processo = db.session.get(ProcessoDisciplina, processo_id)
        if not processo:
            return False, "Processo não encontrado."
        
        try:
            historico_para_deletar = db.session.scalars(select(HistoricoAluno).where(
                HistoricoAluno.aluno_id == processo.aluno_id,
                HistoricoAluno.descricao.like(f"%Abertura de processo: {processo.fato_constatado[:50]}%")
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