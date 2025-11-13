# backend/services/justica_service.py

# ### INÍCIO DA ALTERAÇÃO ###
# Importar 'render_template' não é mais necessário aqui, mas url_for é.
# Importar 'EmailService' para enviá-lo
from flask import g, url_for, session, render_template # render_template é usado no FADA
from ..services.email_service import EmailService
# ### FIM DA ALTERAÇÃO ###

from sqlalchemy import select, func, and_
from datetime import datetime, timezone
from ..models.database import db
from ..models.aluno import Aluno
from ..models.user import User
from ..models.turma import Turma
from ..models.user_school import UserSchool
from ..models.processo_disciplina import ProcessoDisciplina
from ..models.fada_avaliacao import FadaAvaliacao
from ..services.notification_service import NotificationService
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError

class JusticaService:
    
    @staticmethod
    def get_processos_para_usuario(user):
        """Busca processos relevantes para o usuário (admin vê todos, aluno vê só os seus)."""
        if user.role in ['admin_escola', 'super_admin', 'programador']:
            
            school_id_to_load = None
            if user.role in ['super_admin', 'programador']:
                school_id_to_load = session.get('view_as_school_id')
            elif hasattr(user, 'user_schools') and user.user_schools:
                school_id_to_load = user.user_schools[0].school_id

            if not school_id_to_load:
                return [] 
            
            query = (
                select(ProcessoDisciplina)
                .join(Aluno, ProcessoDisciplina.aluno_id == Aluno.id)
                .join(User, Aluno.user_id == User.id)
                .join(UserSchool, User.id == UserSchool.user_id) 
                .where(UserSchool.school_id == school_id_to_load) 
                .options(
                    joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user),
                    joinedload(ProcessoDisciplina.relator)
                )
                .order_by(ProcessoDisciplina.data_ocorrencia.desc())
            )
        else:
            # Assumindo que o perfil do aluno está em user.aluno_profile
            if not user.aluno_profile:
                return [] # Retorna vazio se o usuário não for um aluno
            
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
        
        # ### CORREÇÃO: Busca o 'aluno.user' para passar aos serviços
        aluno_user = aluno.user
        if not aluno_user or not aluno_user.email:
             return False, "Este aluno não possui um usuário ou e-mail associado. Não é possível notificá-lo."

        try:
            novo_processo = ProcessoDisciplina(
                aluno_id=aluno_id,
                relator_id=relator_id,
                fato_constatado=fato,
                observacao=observacao,
                pontos=pontos,
                status='Aguardando Ciência' 
            )
            db.session.add(novo_processo)
            
            # ######################################################
            # ### INÍCIO DA CORREÇÃO DE HOJE ###
            # ######################################################
            # Força o banco a popular os defaults (como ID e data_ocorrencia)
            # ANTES de passar o objeto 'novo_processo' para o template de e-mail.
            db.session.flush()
            # ######################################################
            # ### FIM DA CORREÇÃO DE HOJE ###
            # ######################################################

            # ### INÍCIO DA CORREÇÃO ANTERIOR (E-MAIL) ###
            # 1. Gerar a URL para os links
            url_notificacao = url_for('justica.index', _external=True)

            # 2. Enviar o e-mail para o aluno usando o serviço correto
            # O EmailService já tem o template e as variáveis corretas (incluindo 'user')
            EmailService.send_justice_notification_email(
                user=aluno_user,
                processo=novo_processo, # Agora 'novo_processo' tem a data_ocorrencia
                url=url_notificacao
            )
            # ### FIM DA CORREÇÃO ANTERIOR (E-MAIL) ###

            # 3. Criar a notificação interna (sininho)
            NotificationService.create_notification(
                user_id=aluno_user.id,
                message=f"Novo Processo Disciplinar: {fato}", 
                url=url_notificacao
            )
            
            # 4. Salvar tudo no banco
            db.session.commit()
            
            return True, "Processo disciplinar registrado e aluno notificado por e-mail e notificação interna!"
        
        except SQLAlchemyError as e:
            db.session.rollback()
            return False, f"Erro de banco de dados: {e}"
        except Exception as e:
            db.session.rollback()
            # Este 'except' pega o erro 'strftime'
            return False, f"Erro inesperado ao criar processo (verifique as configurações de e-mail): {e}"

    @staticmethod
    def registrar_ciente(processo_id, user):
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
            
        if processo.status not in ['Defesa Enviada', 'Aluno Notificado', 'Aguardando Ciência']:
             return False, "Este processo não está em fase de finalização."
        
        aluno_user = getattr(getattr(processo, 'aluno', None), 'user', None)
        if not aluno_user or not aluno_user.email:
             return False, "Não foi possível encontrar o usuário ou e-mail do aluno para notificar."

        try:
            processo.decisao_final = decisao
            processo.fundamentacao = fundamentacao
            processo.detalhes_sancao = detalhes_sancao
            processo.data_decisao = datetime.now(timezone.utc)
            processo.status = 'Finalizado'
            
            # ### INÍCIO DA CORREÇÃO ANTERIOR (E-MAIL) ###
            # Envia e-mail de notificação da decisão usando o serviço correto
            EmailService.send_justice_verdict_email(
                user=aluno_user,
                processo=processo
            )
            # ### FIM DA CORREÇÃO ANTERIOR (E-MAIL) ###

            # Cria notificação interna
            NotificationService.create_notification(
                user_id=aluno_user.id,
                message=f"Seu processo nº {processo.id} foi finalizado. Decisão: {decisao}.",
                url=url_for('justica.index', _external=True)
            )
            
            # O flush não é necessário aqui, pois o commit() vem antes de qualquer erro
            db.session.commit()
            
            return True, "Processo finalizado e aluno notificado por e-mail!"
        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao finalizar processo (verifique as configurações de e-mail): {e}"

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
        
    # ### INÍCIO DAS NOVAS FUNÇÕES FADA ###

    @staticmethod
    def get_alunos_para_fada(school_id):
        """Busca todos os alunos de uma escola para a lista da FADA."""
        query = (
            select(Aluno)
            .join(User, Aluno.user_id == User.id)
            .join(UserSchool, User.id == UserSchool.user_id)
            .where(
                UserSchool.school_id == school_id,
                User.role == 'aluno'
            )
            .options(joinedload(Aluno.user)) # Carrega os dados do usuário
            .order_by(User.nome_completo)
        )
        return db.session.scalars(query).all()

    @staticmethod
    def get_fada_por_id(avaliacao_id):
        """Busca uma avaliação FADA específica pelo ID, com dados do aluno e avaliador."""
        query = (
            select(FadaAvaliacao)
            .where(FadaAvaliacao.id == avaliacao_id)
            .options(
                joinedload(FadaAvaliacao.aluno).joinedload(Aluno.user),
                joinedload(FadaAvaliacao.avaliador)
            )
        )
        return db.session.scalar(query)

    @staticmethod
    # ### CORREÇÃO DE BUG ANTERIOR: Adicionado 'nome_avaliador_custom' que estava faltando ###
    def salvar_fada(form_data, aluno_id, avaliador_id, nome_avaliador_custom):
        """Cria ou atualiza uma avaliação FADA para um aluno."""
        try:
            # ### CORREÇÃO DE BUG ANTERIOR: Passa o 'nome_avaliador_custom' para o modelo ###
            avaliacao = FadaAvaliacao(
                aluno_id=aluno_id, 
                avaliador_id=avaliador_id,
                nome_avaliador_custom=nome_avaliador_custom
            )

            # Mapeia os 18 atributos
            for i in range(1, 19):
                field_name_map = {
                    1: 'attr_1_expressao', 2: 'attr_2_planejamento', 3: 'attr_3_perseveranca',
                    4: 'attr_4_apresentacao', 5: 'attr_5_lealdade', 6: 'attr_6_tato',
                    7: 'attr_7_equilibrio', 8: 'attr_8_disciplina', 9: 'attr_9_responsabilidade',
                    10: 'attr_10_maturidade', 11: 'attr_11_assiduidade', 12: 'attr_12_pontualidade',
                    13: 'attr_13_diccao', 14: 'attr_14_lideranca', 15: 'attr_15_relacionamento',
                    16: 'attr_16_etica', 17: 'attr_17_produtividade', 18: 'attr_18_eficiencia'
                }
                field_name = field_name_map.get(i)
                form_field_name = f'attr_{i}' # O nome no formulário é 'attr_1', 'attr_2', etc.
                
                valor = form_data.get(form_field_name)
                try:
                    valor_float = float(valor)
                    valor_float = max(0.0, min(10.0, valor_float))
                except (ValueError, TypeError):
                    valor_float = 8.0 # Padrão
                
                if field_name:
                    setattr(avaliacao, field_name, valor_float)

            # Preenche os campos de texto
            avaliacao.justificativa_notas = form_data.get('justificativa_notas')
            avaliacao.observacoes = form_data.get('observacoes')
            avaliacao.adaptacao_carreira = form_data.get('adaptacao_carreira', 'Em adaptação à carreira militar')

            db.session.add(avaliacao)
            db.session.commit()
            
            return True, "Avaliação FADA salva com sucesso.", avaliacao.id
        
        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao salvar a avaliação FADA: {e}", None
            
    # ### FIM DAS NOVAS FUNÇÕES FADA ###