# backend/services/justica_service.py

# --- CORREÇÃO: Importar 'session' ---
from flask import g, url_for, session
from sqlalchemy import select, func, and_
from datetime import datetime, timezone
from ..models.database import db
from ..models.aluno import Aluno
from ..models.user import User
from ..models.turma import Turma
from ..models.user_school import UserSchool # <-- Importação necessária
from ..models.processo_disciplina import ProcessoDisciplina
# ### INÍCIO DA ALTERAÇÃO (FADA) ###
from ..models.fada_avaliacao import FadaAvaliacao 
# ### FIM DA ALTERAÇÃO ###
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

    # ... (registrar_ciente, enviar_defesa, finalizar_processo, deletar_processo, ... ) ...
    # ... (MANTENHA TODAS AS SUAS FUNÇÕES EXISTENTES AQUI) ...

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
            .order_by(User.nome_completo)
        )
        return db.session.scalars(query).all()

    @staticmethod
    def get_fada_por_id(avaliacao_id):
        """Busca uma avaliação FADA específica pelo ID."""
        return db.session.get(FadaAvaliacao, avaliacao_id)

    @staticmethod
    def salvar_fada(form_data, aluno_id, avaliador_id):
        """Cria ou atualiza uma avaliação FADA para um aluno."""
        try:
            # Tenta encontrar uma FADA existente para este aluno (pode ser usado para editar)
            # Por simplicidade, vamos criar uma nova a cada vez.
            # avaliacao = db.session.scalar(select(FadaAvaliacao).where(FadaAvaliacao.aluno_id == aluno_id))
            # if not avaliacao:
            #     avaliacao = FadaAvaliacao(aluno_id=aluno_id)
            
            # Nova avaliação sempre
            avaliacao = FadaAvaliacao(aluno_id=aluno_id, avaliador_id=avaliador_id)

            # Preenche os 18 atributos
            for i in range(1, 19):
                field_name = f'attr_{i}'
                form_field_name = f'attr_{i}_expressao' if i == 1 else \
                                  f'attr_{i}_planejamento' if i == 2 else \
                                  f'attr_{i}_perseveranca' if i == 3 else \
                                  f'attr_{i}_apresentacao' if i == 4 else \
                                  f'attr_{i}_lealdade' if i == 5 else \
                                  f'attr_{i}_tato' if i == 6 else \
                                  f'attr_{i}_equilibrio' if i == 7 else \
                                  f'attr_{i}_disciplina' if i == 8 else \
                                  f'attr_{i}_responsabilidade' if i == 9 else \
                                  f'attr_{i}_maturidade' if i == 10 else \
                                  f'attr_{i}_assiduidade' if i == 11 else \
                                  f'attr_{i}_pontualidade' if i == 12 else \
                                  f'attr_{i}_diccao' if i == 13 else \
                                  f'attr_{i}_lideranca' if i == 14 else \
                                  f'attr_{i}_relacionamento' if i == 15 else \
                                  f'attr_{i}_etica' if i == 16 else \
                                  f'attr_{i}_produtividade' if i == 17 else \
                                  f'attr_{i}_eficiencia' # 18
                
                # O nome no form é só attr_1, attr_2, etc.
                form_field_name = f'attr_{i}'
                
                # Pega o valor do form, converte para float, e usa 8.0 como padrão
                valor = form_data.get(form_field_name)
                try:
                    valor_float = float(valor)
                except (ValueError, TypeError):
                    valor_float = 8.0 # Padrão
                
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