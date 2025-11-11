# backend/services/justica_service.py

# --- CORREÇÃO: Importar 'session' ---
from flask import g, url_for, session
from sqlalchemy import select, func
from datetime import datetime, timezone
from ..models.database import db
from ..models.aluno import Aluno
from ..models.user import User
from ..models.turma import Turma
from ..models.user_school import UserSchool # <-- Importação necessária
from ..models.processo_disciplina import ProcessoDisciplina
from ..services.notification_service import NotificationService
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError

class JusticaService:
    
    @staticmethod
    def get_processos_para_usuario(user):
        """Busca processos relevantes para o usuário (admin vê todos, aluno vê só os seus)."""
        if user.role in ['admin_escola', 'super_admin', 'programador']:
            
            # --- INÍCIO DA CORREÇÃO ---
            # Busca a escola ativa manualmente a partir da session e do user.
            # Não podemos confiar em 'g' (Flask global) dentro da camada de serviço.
            school_id_to_load = None
            if user.role in ['super_admin', 'programador']:
                school_id_to_load = session.get('view_as_school_id')
            elif hasattr(user, 'user_schools') and user.user_schools:
                school_id_to_load = user.user_schools[0].school_id

            if not school_id_to_load:
                return [] # Retorna vazio se nenhuma escola for encontrada
            # --- FIM DA CORREÇÃO ---
            
            # A consulta agora filtra pelo UserSchool (vínculo do usuário com a escola).
            query = (
                select(ProcessoDisciplina)
                .join(Aluno, ProcessoDisciplina.aluno_id == Aluno.id)
                .join(User, Aluno.user_id == User.id)
                .join(UserSchool, User.id == UserSchool.user_id) # Filtra pelo vínculo do User
                .where(UserSchool.school_id == school_id_to_load) # <-- USA A VARIÁVEL CORRETA
                .options(
                    joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user),
                    joinedload(ProcessoDisciplina.relator)
                )
                .order_by(ProcessoDisciplina.data_ocorrencia.desc())
            )
        else:
            # Query para Aluno (sempre esteve correta)
            query = (
                select(ProcessoDisciplina)
                .where(ProcessoDisciplina.aluno_id == user.aluno_profile.id)
                .options(
                    joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user),
                    joinedload(ProcessoDisciplina.relator)
                )
                .order_by(ProcessoDisciplina.data_ocorrencia.desc())
            )
            
        return db.session.scalars(query).all()

    @staticmethod
    def criar_processo(fato, observacao, aluno_id, relator_id, pontos: float = 0.0):
        aluno = db.session.get(Aluno, aluno_id)
        if not aluno:
            return False, "Aluno não encontrado."
        
        if not aluno.user_id:
             return False, "Este aluno não possui um usuário associado. Não é possível notificá-lo."

        try:
            novo_processo = ProcessoDisciplina(
                aluno_id=aluno_id,
                relator_id=relator_id,
                fato_constatado=fato,
                observacao=observacao,
                pontos=pontos,
                status='Aguardando Ciência' # Status inicial correto
            )
            db.session.add(novo_processo)
            db.session.commit()
            
            # O NotificationService não aceita 'title', apenas 'message'.
            NotificationService.create_notification(
                user_id=aluno.user_id,
                message=f"Novo Processo Disciplinar: {fato}", # Título incluído na mensagem
                url=url_for('justica.index', _external=True)
            )
            
            return True, "Processo disciplinar registrado e aluno notificado com sucesso!"
        
        except SQLAlchemyError as e:
            db.session.rollback()
            return False, f"Erro de banco de dados: {e}"
        except Exception as e:
            db.session.rollback()
            return False, f"Erro inesperado ao criar processo: {e}"

    @staticmethod
    def registrar_ciente(processo_id, user):
        """Aluno clica no botão 'Estou Ciente'."""
        processo = db.session.get(ProcessoDisciplina, processo_id)
        if not processo or processo.aluno_id != user.aluno_profile.id:
            return False, "Processo não encontrado ou não pertence a você."
        
        if processo.status != 'Aguardando Ciência':
            return False, "Este processo não está mais aguardando ciência."
            
        try:
            processo.status = 'Aluno Notificado'
            processo.data_ciente = datetime.now(timezone.utc)
            db.session.commit()
            
            NotificationService.create_notification(
                user_id=processo.relator_id,
                message=f"O aluno {user.nome_completo} deu ciência do Processo nº {processo.id}.",
                url=url_for('justica.index', _external=True)
            )
            
            return True, "Ciência registrada com sucesso. Você tem 24h para apresentar sua defesa."
        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao registrar ciência: {e}"

    @staticmethod
    def enviar_defesa(processo_id, defesa, user):
        processo = db.session.get(ProcessoDisciplina, processo_id)
        if not processo or processo.aluno_id != user.aluno_profile.id:
            return False, "Processo não encontrado ou não pertence a você."

        if processo.status != 'Aluno Notificado':
            return False, "O prazo para defesa expirou ou a defesa já foi enviada."

        try:
            processo.defesa = defesa
            processo.data_defesa = datetime.now(timezone.utc)
            processo.status = 'Defesa Enviada'
            db.session.commit()
            
            NotificationService.create_notification(
                user_id=processo.relator_id,
                message=f"O aluno {user.nome_completo} enviou a defesa para o Processo nº {processo.id}.",
                url=url_for('justica.index', _external=True)
            )
            
            return True, "Defesa enviada com sucesso."
        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao enviar defesa: {e}"
            
    @staticmethod
    def finalizar_processo(processo_id, decisao, fundamentacao, detalhes_sancao):
        processo = db.session.get(ProcessoDisciplina, processo_id)
        if not processo:
            return False, "Processo não encontrado."
            
        if processo.status not in ['Defesa Enviada', 'Aluno Notificado']:
            return False, "Este processo não está em fase de finalização."
            
        try:
            processo.decisao_final = decisao
            processo.fundamentacao = fundamentacao
            processo.detalhes_sancao = detalhes_sancao
            processo.data_decisao = datetime.now(timezone.utc)
            processo.status = 'Finalizado'
            
            db.session.commit()
            
            NotificationService.create_notification(
                user_id=processo.aluno.user_id,
                message=f"Seu processo nº {processo.id} foi finalizado. Decisão: {decisao}.",
                url=url_for('justica.index', _external=True)
            )
            
            return True, "Processo finalizado com sucesso!"
        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao finalizar processo: {e}"

    @staticmethod
    def deletar_processo(processo_id):
        processo = db.session.get(ProcessoDisciplina, processo_id)
        if not processo:
            return False, "Processo não encontrado."

        if processo.status != 'Aguardando Ciência':
            return False, "Não é possível excluir um processo após o aluno dar ciência."
            
        try:
            db.session.delete(processo)
            db.session.commit()
            return True, "Processo excluído com sucesso."
        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao excluir processo: {e}"
            
    @staticmethod
    def get_processos_por_ids(ids):
        query = select(ProcessoDisciplina).where(ProcessoDisciplina.id.in_(ids))
        return db.session.scalars(query).all()
        
    @staticmethod
    def get_finalized_processos():
        active_school = g.get('active_school')
        if not active_school:
            return []
        
        # Subquery para filtrar pela escola (via UserSchool)
        alunos_da_escola = (
            select(Aluno.id)
            .join(User, Aluno.user_id == User.id)
            .join(UserSchool, User.id == UserSchool.user_id)
            .where(UserSchool.school_id == active_school.id)
        ).subquery()
        
        query = (
            select(ProcessoDisciplina)
            .join(alunos_da_escola, ProcessoDisciplina.aluno_id == alunos_da_escola.c.id)
            .where(ProcessoDisciplina.status == 'Finalizado')
            .order_by(ProcessoDisciplina.data_decisao.desc())
        )
        return db.session.scalars(query).all()

    @staticmethod
    def get_analise_disciplinar_data():
        active_school = g.get('active_school')
        if not active_school:
            return {}

        # Subquery para filtrar pela escola (via UserSchool)
        alunos_da_escola = (
            select(Aluno.id)
            .join(User, Aluno.user_id == User.id)
            .join(UserSchool, User.id == UserSchool.user_id)
            .where(UserSchool.school_id == active_school.id)
        ).subquery()

        status_counts = db.session.execute(
            select(ProcessoDisciplina.status, func.count(ProcessoDisciplina.id))
            .join(alunos_da_escola, ProcessoDisciplina.aluno_id == alunos_da_escola.c.id)
            .group_by(ProcessoDisciplina.status)
        ).all()
        
        common_facts = db.session.execute(
            select(ProcessoDisciplina.fato_constatado, func.count(ProcessoDisciplina.id).label('total'))
            .join(alunos_da_escola, ProcessoDisciplina.aluno_id == alunos_da_escola.c.id)
            .group_by(ProcessoDisciplina.fato_constatado)
            .order_by(func.count(ProcessoDisciplina.id).desc())
            .limit(10)
        ).all()
        
        top_alunos = db.session.execute(
            select(User.nome_completo, func.count(ProcessoDisciplina.id).label('total'))
            .join(alunos_da_escola, ProcessoDisciplina.aluno_id == alunos_da_escola.c.id)
            .join(Aluno, ProcessoDisciplina.aluno_id == Aluno.id)
            .join(User, Aluno.user_id == User.id)
            .group_by(User.nome_completo)
            .order_by(func.count(ProcessoDisciplina.id).desc())
            .limit(10)
        ).all()

        return {
            'status_counts': [{'status': s[0], 'total': s[1]} for s in status_counts],
            'common_facts': [{'fato': f[0], 'total': f[1]} for f in common_facts],
            'top_alunos': [{'nome': a[0], 'total': a[1]} for a in top_alunos]
        }