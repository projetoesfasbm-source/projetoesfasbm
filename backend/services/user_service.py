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

        if not matricula or not role:
            return False, "Matrícula e Função são obrigatórios."

        if not school_id:
            return False, "A escola é obrigatória para o pré-cadastro."

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
                db.session.commit()
                return True, f"Usuário {matricula} existente foi vinculado a esta escola como {role}."
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Erro ao vincular usuário existente: {e}")
                return False, "Erro ao vincular usuário existente."
        
        try:
            new_user = User(matricula=matricula, role=role, is_active=False)
            db.session.add(new_user)
            db.session.flush()
            
            db.session.add(UserSchool(user_id=new_user.id, school_id=school_id, role=role))
            db.session.commit()
            return True, f"Usuário {matricula} pré-cadastrado com sucesso como {role}."
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro no pré-cadastro novo: {e}")
            return False, "Erro ao pré-cadastrar novo usuário."

    @staticmethod
    def batch_pre_register_users(matriculas, role, school_id):
        if not role:
            return False, 0, 0

        novos = 0
        existentes = 0

        for m in matriculas:
            matricula = normalize_matricula(m)
            if not matricula:
                continue

            user = db.session.scalar(select(User).filter_by(matricula=matricula))
            if user:
                link = db.session.scalar(select(UserSchool).filter_by(user_id=user.id, school_id=school_id))
                if not link:
                    db.session.add(UserSchool(user_id=user.id, school_id=school_id, role=role))
                    existentes += 1
                else:
                    existentes += 1
                continue

            try:
                new_user = User(matricula=matricula, role=role, is_active=False)
                db.session.add(new_user)
                db.session.flush()
                db.session.add(UserSchool(user_id=new_user.id, school_id=school_id, role=role))
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
    def assign_school_role(user_id, school_id, role):
        user = db.session.get(User, user_id)
        if not user: return False, "Usuário não encontrado."
        
        if (user.username or '') in ['super_admin', 'programador'] or user.role in ['super_admin', 'programador']:
            return False, "Não permitido alterar usuário privilegiado."

        user.role = role
        existing = db.session.scalar(select(UserSchool).filter_by(user_id=user_id, school_id=school_id))
        
        if existing:
            existing.role = role
        else:
            db.session.add(UserSchool(user_id=user_id, school_id=school_id, role=role))

        try:
            db.session.commit()
            return True, "Função atribuída com sucesso."
        except IntegrityError:
            db.session.rollback()
            return False, "Erro de integridade."

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
    def get_current_school_id():
        """
        Retorna a escola atual baseada ESTRITAMENTE na sessão ou seleção explícita.
        NÃO faz fallback automático para a primeira escola se houver dúvida.
        """
        if not current_user.is_authenticated:
            return None

        # 1. Modo Visualização (Super Admin)
        if getattr(current_user, 'role', '') in ['super_admin', 'programador']:
            view_as = session.get('view_as_school_id')
            if view_as:
                return int(view_as)

        # 2. Verifica a Sessão Gravada com Validação no Banco
        active_id = session.get('active_school_id')
        
        if active_id:
            try:
                active_id_int = int(active_id)
                # Validação Rápida: O usuário ainda tem vínculo com essa escola?
                # Consultamos o banco para garantir (Isolamento Forte)
                has_link = db.session.scalar(
                    select(UserSchool.school_id).where(
                        UserSchool.user_id == current_user.id,
                        UserSchool.school_id == active_id_int
                    )
                )
                if has_link:
                    return active_id_int
                else:
                    # Se tinha na sessão mas perdeu o vínculo no banco, limpa a sessão.
                    session.pop('active_school_id', None)
            except Exception:
                pass

        # 3. Fallback Seguro: 
        # Se tem APENAS UM vínculo, usa ele (usuário comum de 1 escola). 
        # Se tiver 2 ou mais, RETORNA NONE para forçar a tela de seleção (evita o erro do fallback).
        all_links = db.session.execute(
            select(UserSchool).where(UserSchool.user_id == current_user.id)
        ).scalars().all()

        if len(all_links) == 1:
            chosen_id = all_links[0].school_id
            session['active_school_id'] = chosen_id
            return chosen_id
            
        # Caso complexo: tem 0 ou >1 escolas e nada na sessão.
        # Retorna None. O Controller deve redirecionar para /selecionar-escola.
        return None

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