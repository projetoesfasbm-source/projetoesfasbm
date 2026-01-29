# backend/services/user_service.py

from flask import current_app, session, has_request_context
from flask_login import current_user
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from ..models.database import db
from ..models.user import User
from ..models.user_school import UserSchool
from ..models.instrutor import Instrutor
from ..models.aluno import Aluno
from ..models.horario import Horario
from ..models.diario_classe import DiarioClasse
from ..models.disciplina_turma import DisciplinaTurma
from utils.normalizer import normalize_matricula
import logging

logger = logging.getLogger(__name__)

class UserService:

    @staticmethod
    def get_current_school_id():
        """
        Retorna o ID da escola ativa na sessão ou baseada no contexto do usuário.
        """
        if not has_request_context(): return None
        if not current_user or not current_user.is_authenticated: return None

        # Super Admins e Programadores podem ter uma escola "Visualizar Como"
        if getattr(current_user, 'role', '') in ['super_admin', 'programador']:
            view_as = session.get('view_as_school_id')
            if view_as: return int(view_as)

        # Tenta pegar da sessão
        active_id = session.get('active_school_id')
        if active_id:
            try:
                active_id_int = int(active_id)
                # Verifica se o usuário AINDA tem acesso a essa escola no banco
                has_link = db.session.scalar(
                    select(UserSchool.school_id).where(
                        UserSchool.user_id == current_user.id,
                        UserSchool.school_id == active_id_int
                    )
                )
                if has_link: return active_id_int
                else: session.pop('active_school_id', None)
            except Exception: pass

        # Se não tiver na sessão, tenta pegar a única escola disponível
        all_links = db.session.execute(
            select(UserSchool).where(UserSchool.user_id == current_user.id)
        ).scalars().all()

        if len(all_links) == 1:
            chosen_id = all_links[0].school_id
            session['active_school_id'] = chosen_id
            return chosen_id
            
        return None

    @staticmethod
    def _ensure_instrutor_profile(user_id, school_id):
        """
        Garante que exista um perfil de Instrutor para o usuário nesta escola específica.
        """
        if not school_id: return False
        try:
            exists = db.session.scalar(
                select(Instrutor).filter_by(user_id=user_id, school_id=school_id)
            )
            if not exists:
                # Tenta copiar dados de outro perfil existente para facilitar
                other_profile = db.session.scalar(
                    select(Instrutor).filter_by(user_id=user_id).limit(1)
                )
                
                new_profile = Instrutor(
                    user_id=user_id,
                    school_id=school_id,
                    telefone=other_profile.telefone if other_profile else None,
                    is_rr=other_profile.is_rr if other_profile else False,
                    foto_perfil=other_profile.foto_perfil if other_profile else 'default.png'
                )
                db.session.add(new_profile)
                return True
        except Exception as e:
            current_app.logger.error(f"Erro ao criar perfil automático de instrutor: {e}")
        return False

    @staticmethod
    def _ensure_user_school(user_id, school_id, role):
        """
        MÉTODO CENTRAL DE VINCULAÇÃO.
        Garante que o usuário tenha o vínculo com a escola ESPECÍFICA solicitada.
        NÃO afeta vínculos com outras escolas.
        """
        if not school_id: return False

        # Verifica se já existe O vínculo nesta escola específica
        existing_link = db.session.scalar(
            select(UserSchool).where(
                UserSchool.user_id == user_id,
                UserSchool.school_id == school_id
            )
        )
        
        if existing_link:
            # Se já existe, apenas garante que o papel está atualizado
            if existing_link.role != role:
                existing_link.role = role
            return True # Já estava vinculado

        # Se não existe vínculo COM ESTA ESCOLA, cria um novo.
        new_link = UserSchool(user_id=user_id, school_id=school_id, role=role)
        db.session.add(new_link)
        return True

    @staticmethod
    def pre_register_user(data, school_id):
        matricula = normalize_matricula(data.get('matricula'))
        role = (data.get('role') or 'aluno').strip()

        if not matricula:
            return False, "Matrícula é obrigatória."
        if not school_id:
            return False, "A escola é obrigatória para o vínculo."

        try:
            # 1. Busca ou Cria o Usuário Globalmente
            user = db.session.scalar(select(User).filter_by(matricula=matricula))

            is_new_user = False
            if not user:
                is_new_user = True
                user = User(
                    matricula=matricula,
                    username=matricula, # Temporário
                    role=role,
                    is_active=True, # Pré-cadastro já ativa para login
                    must_change_password=True
                )
                user.set_password(matricula) # Senha inicial = matrícula
                db.session.add(user)
                db.session.flush() # Gera ID

                # CORREÇÃO DO ERRO 'opm required': Passamos um valor padrão '-'
                if role == 'aluno':
                    db.session.add(Aluno(user_id=user.id, opm='-'))

            # 2. Garante o Vínculo SOMENTE com a Escola Solicitada
            # Se ele já existir em outra escola, isso não afeta nada aqui.
            UserService._ensure_user_school(user.id, school_id, role)

            # 3. Se for instrutor, garante o perfil de instrutor nesta escola
            if role == 'instrutor':
                UserService._ensure_instrutor_profile(user.id, school_id)

            db.session.commit()

            msg = "Usuário criado e vinculado." if is_new_user else "Usuário existente vinculado a esta escola."
            return True, msg

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro no pré-cadastro: {e}")
            return False, f"Erro interno: {str(e)}"

    @staticmethod
    def batch_pre_register_users(matriculas, role, school_id):
        if not role or not school_id: return False, 0, 0

        novos = 0
        existentes = 0

        try:
            for m in matriculas:
                matricula = normalize_matricula(m)
                if not matricula: continue

                user = db.session.scalar(select(User).filter_by(matricula=matricula))
                
                if user:
                    # Usuário existe: Apenas garante o vínculo com ESTA escola
                    UserService._ensure_user_school(user.id, school_id, role)
                    if role == 'instrutor':
                        UserService._ensure_instrutor_profile(user.id, school_id)
                    existentes += 1
                else:
                    # Usuário novo: Cria e vincula
                    user = User(
                        matricula=matricula,
                        username=matricula,
                        role=role,
                        is_active=True,
                        must_change_password=True
                    )
                    user.set_password(matricula)
                    db.session.add(user)
                    db.session.flush()
                    
                    # CORREÇÃO DO ERRO 'opm required'
                    if role == 'aluno':
                        db.session.add(Aluno(user_id=user.id, opm='-'))
                    
                    UserService._ensure_user_school(user.id, school_id, role)
                    if role == 'instrutor':
                        UserService._ensure_instrutor_profile(user.id, school_id)
                        
                    novos += 1

            db.session.commit()
            return True, novos, existentes
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro no batch: {e}")
            return False, 0, 0

    @staticmethod
    def create_user(data, school_id=None):
        """
        Criação completa de usuário (geralmente via Admin Tools ou Cadastro Manual).
        """
        try:
            # Verifica duplicidade global
            existing = db.session.scalar(
                select(User).where(or_(User.email == data['email'], User.matricula == data['matricula']))
            )
            if existing: return False, "E-mail ou matrícula já cadastrados no sistema."

            # Define a escola do contexto se não passada
            if not school_id:
                school_id = UserService.get_current_school_id()

            role = data.get('role', 'aluno')
            password = data.get('password') or 'mudar123'

            user = User(
                email=data['email'], 
                matricula=data['matricula'], 
                nome_completo=data['nome_completo'],
                nome_de_guerra=data.get('nome_de_guerra'), 
                role=role,
                posto_graduacao=data.get('posto_graduacao'),
                is_active=True,
                must_change_password=True
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.flush()
            
            # CORREÇÃO DO ERRO 'opm required'
            if role == 'aluno':
                db.session.add(Aluno(user_id=user.id, opm='-'))

            # VINCULAÇÃO
            if school_id and role not in ['programador', 'super_admin']:
                UserService._ensure_user_school(user.id, school_id, role)
                if role == 'instrutor':
                    UserService._ensure_instrutor_profile(user.id, school_id)

            db.session.commit()
            return True, user
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def set_user_role_for_school(user_id, school_id, new_role):
        user = db.session.get(User, user_id)
        if not user: return False, "Usuário não encontrado."
            
        if user.role == User.ROLE_PROGRAMADOR:
             return False, "Não é possível alterar cargo de Programador via escola."

        try:
            # Usa o método centralizado para garantir o vínculo/atualização
            UserService._ensure_user_school(user_id, school_id, new_role)
            
            if new_role == 'instrutor':
                UserService._ensure_instrutor_profile(user_id, school_id)
            
            db.session.commit()
            return True, "Permissão atualizada na escola com sucesso."
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao setar role: {e}")
            return False, "Erro de banco de dados."

    assign_school_role = set_user_role_for_school

    @staticmethod
    def update_user(user_id, data):
        user = db.session.get(User, user_id)
        if not user: return False, "Usuário não encontrado."
        try:
            if 'nome_completo' in data: user.nome_completo = data['nome_completo']
            if 'nome_de_guerra' in data: user.nome_de_guerra = data['nome_de_guerra']
            if 'email' in data: user.email = data['email']
            if 'posto_graduacao' in data: user.posto_graduacao = data['posto_graduacao']
            
            for k, v in data.items():
                 if hasattr(user, k) and k not in ['id', 'password_hash']:
                      setattr(user, k, v)

            db.session.commit()
            return True, "Atualizado."
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def get_users_by_school(school_id):
        try:
            return db.session.scalars(
                select(User)
                .join(User.user_schools)
                .where(UserSchool.school_id == school_id)
                .order_by(User.nome_completo)
            ).all()
        except Exception as e:
            current_app.logger.error(f"Erro ao buscar usuários da escola {school_id}: {e}")
            return []
    
    @staticmethod
    def get_all_users():
        return User.query.all()

    @staticmethod
    def get_by_id(user_id):
        return db.session.get(User, user_id)
    
    @staticmethod
    def get_user_by_id(user_id):
        return db.session.get(User, user_id)

    @staticmethod
    def get_user_by_username(username):
        return User.query.filter_by(username=username).first()

    @staticmethod
    def remove_school_role(user_id, school_id):
        user = db.session.get(User, user_id)
        if user and user.role in ['super_admin', 'programador']:
            return False, "Não permitido."

        assignment = db.session.scalar(select(UserSchool).filter_by(user_id=user_id, school_id=school_id))
        if not assignment:
            return False, "Vínculo não encontrado."

        db.session.delete(assignment)
        db.session.commit()
        return True, "Vínculo removido."

    @staticmethod
    def delete_user_by_id(user_id):
        return UserService.delete_user(user_id)

    @staticmethod
    def delete_user(user_id):
        """
        Exclusão profunda de usuário.
        """
        try:
            user = db.session.get(User, user_id)
            if not user: return False, "Usuário não encontrado."
            
            if user.role in ['super_admin', 'programador'] and (not current_user or current_user.role != 'programador'):
                 return False, "Não é permitido excluir administradores globais."

            # Limpezas profundas
            # 1. Instrutor
            instrutores = Instrutor.query.filter_by(user_id=user.id).all()
            for instrutor in instrutores:
                DisciplinaTurma.query.filter_by(instrutor_id_1=instrutor.id).update({'instrutor_id_1': None})
                DisciplinaTurma.query.filter_by(instrutor_id_2=instrutor.id).update({'instrutor_id_2': None})
                Horario.query.filter_by(instrutor_id=instrutor.id).delete()
                Horario.query.filter_by(instrutor_id_2=instrutor.id).update({'instrutor_id_2': None})
                db.session.delete(instrutor)

            # 2. Aluno
            aluno = db.session.scalar(select(Aluno).filter_by(user_id=user.id))
            if aluno: db.session.delete(aluno)

            # 3. Vínculos e Diários
            DiarioClasse.query.filter_by(responsavel_id=user.id).update({'responsavel_id': None})
            DiarioClasse.query.filter_by(instrutor_assinante_id=user.id).update({'instrutor_assinante_id': None})
            db.session.query(UserSchool).filter(UserSchool.user_id == user.id).delete()

            db.session.delete(user)
            db.session.commit()
            return True, "Usuário excluído com sucesso."

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao excluir usuário {user_id}: {str(e)}")
            return False, f"Erro ao excluir: {str(e)}"