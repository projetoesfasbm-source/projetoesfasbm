# backend/services/user_service.py

from flask import current_app, session, has_request_context
from flask_login import current_user
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError

from ..models.database import db
from ..models.user import User
from ..models.user_school import UserSchool
from ..models.instrutor import Instrutor 
from utils.normalizer import normalize_matricula

class UserService:

    @staticmethod
    def _ensure_instrutor_profile(user_id, school_id):
        """
        Função auxiliar interna: Garante que exista um perfil de Instrutor
        para o usuário nesta escola. Se não existir, cria um padrão.
        """
        try:
            exists = db.session.scalar(
                select(Instrutor).filter_by(user_id=user_id, school_id=school_id)
            )
            if not exists:
                # Tenta copiar dados de outro perfil existente (opcional) ou usa padrão
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
    def pre_register_user(data, school_id):
        matricula = normalize_matricula(data.get('matricula'))
        role = (data.get('role') or '').strip()

        if not matricula or not role:
            return False, "Matrícula e Função são obrigatórios."
        if not school_id:
            return False, "A escola é obrigatória."

        existing_user = db.session.scalar(select(User).filter_by(matricula=matricula))

        if existing_user:
            existing_link = db.session.scalar(
                select(UserSchool).filter_by(user_id=existing_user.id, school_id=school_id)
            )
            if existing_link:
                return False, f"O usuário {matricula} já está vinculado a esta escola."
            
            try:
                new_assignment = UserSchool(user_id=existing_user.id, school_id=school_id, role=role)
                db.session.add(new_assignment)
                
                if role == 'instrutor':
                    UserService._ensure_instrutor_profile(existing_user.id, school_id)
                
                db.session.commit()
                return True, f"Usuário {matricula} vinculado a esta escola como {role}."
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Erro ao vincular: {e}")
                return False, "Erro ao vincular."
        
        try:
            new_user = User(matricula=matricula, role='aluno', is_active=False)
            db.session.add(new_user)
            db.session.flush()
            
            db.session.add(UserSchool(user_id=new_user.id, school_id=school_id, role=role))
            
            if role == 'instrutor':
                UserService._ensure_instrutor_profile(new_user.id, school_id)

            db.session.commit()
            return True, f"Usuário {matricula} criado e vinculado como {role}."
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro no pré-cadastro: {e}")
            return False, "Erro ao criar usuário."

    @staticmethod
    def set_user_role_for_school(user_id, school_id, new_role):
        user = db.session.get(User, user_id)
        if not user:
            return False, "Usuário não encontrado."
            
        if user.role == User.ROLE_PROGRAMADOR:
             return False, "Não é possível alterar cargo de Programador via escola."

        user_school = db.session.scalar(
            select(UserSchool).filter_by(user_id=user_id, school_id=school_id)
        )

        try:
            if user_school:
                user_school.role = new_role
            else:
                user_school = UserSchool(user_id=user_id, school_id=school_id, role=new_role)
                db.session.add(user_school)
            
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
    def batch_pre_register_users(matriculas, role, school_id):
        if not role: return False, 0, 0

        novos = 0
        existentes = 0

        for m in matriculas:
            matricula = normalize_matricula(m)
            if not matricula: continue

            user = db.session.scalar(select(User).filter_by(matricula=matricula))
            if user:
                link = db.session.scalar(select(UserSchool).filter_by(user_id=user.id, school_id=school_id))
                if not link:
                    db.session.add(UserSchool(user_id=user.id, school_id=school_id, role=role))
                    if role == 'instrutor':
                        UserService._ensure_instrutor_profile(user.id, school_id)
                    existentes += 1
                else:
                    existentes += 1
                continue

            try:
                new_user = User(matricula=matricula, role='aluno', is_active=False)
                db.session.add(new_user)
                db.session.flush()
                db.session.add(UserSchool(user_id=new_user.id, school_id=school_id, role=role))
                if role == 'instrutor':
                    UserService._ensure_instrutor_profile(new_user.id, school_id)
                novos += 1
            except Exception:
                db.session.rollback()
                return False, 0, 0

        try:
            db.session.commit()
            return True, novos, existentes
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro no batch: {e}")
            return False, 0, 0

    @staticmethod
    def get_current_school_id():
        if not has_request_context(): return None
        if not current_user or not current_user.is_authenticated: return None

        if getattr(current_user, 'role', '') in ['super_admin', 'programador']:
            view_as = session.get('view_as_school_id')
            if view_as: return int(view_as)

        active_id = session.get('active_school_id')
        if active_id:
            try:
                active_id_int = int(active_id)
                has_link = db.session.scalar(
                    select(UserSchool.school_id).where(
                        UserSchool.user_id == current_user.id,
                        UserSchool.school_id == active_id_int
                    )
                )
                if has_link: return active_id_int
                else: session.pop('active_school_id', None)
            except Exception: pass

        all_links = db.session.execute(
            select(UserSchool).where(UserSchool.user_id == current_user.id)
        ).scalars().all()

        if len(all_links) == 1:
            chosen_id = all_links[0].school_id
            session['active_school_id'] = chosen_id
            return chosen_id
            
        return None

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
        user = db.session.get(User, user_id)
        if not user: return False, "Usuário não encontrado."
        if user.role in ['super_admin', 'programador']: return False, "Não permitido."
        
        try:
            db.session.delete(user)
            db.session.commit()
            return True, "Usuário excluído."
        except Exception:
            db.session.rollback()
            return False, "Erro ao excluir."
    
    @staticmethod
    def get_by_id(user_id):
        return db.session.get(User, user_id)

    @staticmethod
    def create_user(data, school_id=None):
        """
        Cria um usuário e, CRUCIALMENTE, vincula ele à escola atual.
        Corrigido para evitar criação de alunos órfãos.
        """
        try:
            # Verifica duplicidade
            existing = db.session.scalar(
                select(User).where(or_(User.email == data['email'], User.matricula == data['matricula']))
            )
            if existing: return False, "E-mail ou matrícula já cadastrados."

            # Cria o usuário
            user = User(
                email=data['email'], 
                matricula=data['matricula'], 
                nome_completo=data['nome_completo'],
                nome_de_guerra=data.get('nome_de_guerra'), 
                role=data.get('role', 'aluno'),
                posto_graduacao=data.get('posto_graduacao')
            )
            user.set_password(data['password'])
            
            db.session.add(user)
            db.session.flush() # Gera o ID do usuário
            
            # --- CORREÇÃO DO BUG DO ALUNO ÓRFÃO ---
            # Se school_id não foi passado, tenta pegar da sessão
            if not school_id:
                school_id = UserService.get_current_school_id()
            
            # Se temos uma escola identificada, criamos o vínculo AGORA
            if school_id:
                link_role = data.get('role', 'aluno')
                # Segurança: Programador/SuperAdmin não ganha vínculo automático de aluno
                if link_role not in ['programador', 'super_admin']:
                    user_school = UserSchool(
                        user_id=user.id, 
                        school_id=school_id, 
                        role=link_role
                    )
                    db.session.add(user_school)
                    
                    # Cria perfil extra se for instrutor
                    if link_role == 'instrutor':
                        UserService._ensure_instrutor_profile(user.id, school_id)
            # --------------------------------------

            db.session.commit()
            return True, user
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def update_user(user_id, data):
        user = UserService.get_by_id(user_id)
        if not user: return False, "Usuário não encontrado."
        try:
            if 'nome_completo' in data: user.nome_completo = data['nome_completo']
            if 'nome_de_guerra' in data: user.nome_de_guerra = data['nome_de_guerra']
            if 'email' in data: user.email = data['email']
            if 'posto_graduacao' in data: user.posto_graduacao = data['posto_graduacao']
            db.session.commit()
            return True, "Atualizado."
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    # --- NOVO MÉTODO ADICIONADO ---
    @staticmethod
    def get_users_by_school(school_id):
        """
        Retorna todos os usuários vinculados à escola especificada.
        Utilizado para preencher dropdowns de filtros em logs e relatórios.
        """
        try:
            return db.session.scalars(
                select(User)
                .join(UserSchool)
                .where(UserSchool.school_id == school_id)
                .order_by(User.nome_completo)
            ).all()
        except Exception as e:
            current_app.logger.error(f"Erro ao buscar usuários da escola {school_id}: {e}")
            return []