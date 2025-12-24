# backend/services/user_service.py

from flask import current_app, session
from flask_login import current_user
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..models.database import db
from ..models.user import User
from ..models.user_school import UserSchool
from utils.normalizer import normalize_matricula

class UserService:

    @staticmethod
    def pre_register_user(data, school_id):
        matricula = normalize_matricula(data.get('matricula'))
        role = (data.get('role') or '').strip()
        if not matricula or not role: return False, "Matrícula/Função obrigatórios."
        if not school_id: return False, "Escola obrigatória."

        existing_user = db.session.scalar(select(User).filter_by(matricula=matricula))

        if existing_user:
            existing_link = db.session.scalar(select(UserSchool).filter_by(user_id=existing_user.id, school_id=school_id))
            if existing_link: return False, f"Usuário {matricula} já vinculado."
            
            try:
                db.session.add(UserSchool(user_id=existing_user.id, school_id=school_id, role=role))
                db.session.commit()
                return True, f"Usuário {matricula} vinculado com sucesso."
            except Exception:
                db.session.rollback()
                return False, "Erro ao vincular."
        
        try:
            new_user = User(matricula=matricula, role=role, is_active=False)
            db.session.add(new_user)
            db.session.flush()
            db.session.add(UserSchool(user_id=new_user.id, school_id=school_id, role=role))
            db.session.commit()
            return True, f"Usuário {matricula} pré-cadastrado."
        except Exception:
            db.session.rollback()
            return False, "Erro ao pré-cadastrar."

    @staticmethod
    def batch_pre_register_users(matriculas, role, school_id):
        if not role: return False, 0, 0
        novos, existentes = 0, 0
        for m in matriculas:
            matricula = normalize_matricula(m)
            if not matricula: continue
            user = db.session.scalar(select(User).filter_by(matricula=matricula))
            if user:
                if not db.session.scalar(select(UserSchool).filter_by(user_id=user.id, school_id=school_id)):
                    db.session.add(UserSchool(user_id=user.id, school_id=school_id, role=role))
                    existentes += 1
                else: existentes += 1
                continue
            try:
                new_user = User(matricula=matricula, role=role, is_active=False)
                db.session.add(new_user)
                db.session.flush()
                db.session.add(UserSchool(user_id=new_user.id, school_id=school_id, role=role))
                novos += 1
            except: db.session.rollback()
        try:
            db.session.commit()
            return True, novos, existentes
        except: return False, 0, 0

    @staticmethod
    def assign_school_role(user_id, school_id, role):
        user = db.session.get(User, user_id)
        if not user: return False, "Não encontrado."
        if user.role in ['super_admin', 'programador']: return False, "Não permitido."
        
        existing = db.session.scalar(select(UserSchool).filter_by(user_id=user_id, school_id=school_id))
        if existing: existing.role = role
        else: db.session.add(UserSchool(user_id=user_id, school_id=school_id, role=role))
        
        try: db.session.commit(); return True, "Sucesso."
        except: db.session.rollback(); return False, "Erro."

    @staticmethod
    def remove_school_role(user_id, school_id):
        assignment = db.session.scalar(select(UserSchool).filter_by(user_id=user_id, school_id=school_id))
        if not assignment: return False, "Vínculo não encontrado."
        db.session.delete(assignment)
        db.session.commit()
        return True, "Removido."

    @staticmethod
    def set_active_school(school_id):
        if not current_user.is_authenticated: return False
        link = db.session.scalar(select(UserSchool).where(UserSchool.user_id == current_user.id, UserSchool.school_id == school_id))
        if link or current_user.role in ['super_admin', 'programador']:
            session['active_school_id'] = int(school_id)
            session.permanent = True
            return True
        return False

    @staticmethod
    def get_current_school_id():
        if not current_user.is_authenticated: return None
        if current_user.role in ['super_admin', 'programador']:
            view = session.get('view_as_school_id')
            if view: return int(view)

        active = session.get('active_school_id')
        if active:
            try:
                active_int = int(active)
                # Validação rápida
                if db.session.scalar(select(UserSchool.school_id).where(UserSchool.user_id == current_user.id, UserSchool.school_id == active_int)):
                    return active_int
            except: pass

        # Fallback SEGURO: Só seleciona automático se tiver APENAS UMA escola.
        links = db.session.execute(select(UserSchool).where(UserSchool.user_id == current_user.id)).scalars().all()
        if len(links) == 1:
            session['active_school_id'] = links[0].school_id
            return links[0].school_id
        
        # Se tem mais de 1 e nenhuma na sessão, retorna None para forçar a tela de seleção
        return None

    @staticmethod
    def delete_user_by_id(user_id):
        user = db.session.get(User, user_id)
        if not user or user.role in ['super_admin', 'programador']: return False, "Erro."
        try: db.session.delete(user); db.session.commit(); return True, "Excluído."
        except: db.session.rollback(); return False, "Erro."