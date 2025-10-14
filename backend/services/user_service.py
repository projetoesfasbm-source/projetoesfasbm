# backend/services/user_service.py

from __future__ import annotations

from flask import current_app, session
from flask_login import current_user
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..models.database import db
from ..models.user import User
from ..models.aluno import Aluno
from ..models.user_school import UserSchool
from ..models.school import School
from utils.normalizer import normalize_matricula

class UserService:

    @staticmethod
    def pre_register_user(data, school_id):
        """
        Pré-cadastro unitário: cria User(is_active=False) e vínculo UserSchool(role).
        """
        matricula = normalize_matricula(data.get('matricula'))
        role = (data.get('role') or '').strip()

        if not matricula or not role:
            return False, "Matrícula e Função são obrigatórios."

        if not school_id:
            return False, "A escola é obrigatória para o pré-cadastro."

        if db.session.execute(select(User).filter_by(matricula=matricula)).scalar_one_or_none():
            return False, f"O usuário com Matrícula '{matricula}' já existe."

        try:
            new_user = User(matricula=matricula, role=role, is_active=False)
            db.session.add(new_user)
            db.session.flush()
            db.session.add(UserSchool(user_id=new_user.id, school_id=school_id, role=role))
            db.session.commit()
            return True, f"Usuário {matricula} pré-cadastrado com sucesso como {role}."
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro no pré-cadastro: {e}")
            return False, "Erro ao pré-cadastrar usuário."

    @staticmethod
    def batch_pre_register_users(matriculas, role, school_id):
        """
        Pré-cadastro em lote: cria Users (is_active=False) e vínculos UserSchool(role).
        """
        if not role:
            return False, 0, 0

        novos_usuarios_count = 0
        usuarios_existentes_count = 0

        for m in matriculas:
            matricula = normalize_matricula(m)
            if not matricula:
                continue

            user = db.session.scalar(select(User).filter_by(matricula=matricula))
            if user:
                usuarios_existentes_count += 1
                existing_assignment = db.session.scalar(
                    select(UserSchool).filter_by(user_id=user.id, school_id=school_id)
                )
                if not existing_assignment:
                    db.session.add(UserSchool(user_id=user.id, school_id=school_id, role=role))
                continue

            try:
                new_user = User(matricula=matricula, role=role, is_active=False)
                db.session.add(new_user)
                db.session.flush()
                db.session.add(UserSchool(user_id=new_user.id, school_id=school_id, role=role))
                novos_usuarios_count += 1
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Erro no pré-cadastro em lote para {matricula}: {e}")
                return False, 0, 0

        try:
            db.session.commit()
            return True, novos_usuarios_count, usuarios_existentes_count
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro final no commit do pré-cadastro em lote: {e}")
            return False, 0, 0

    @staticmethod
    def assign_school_role(user_id, school_id, role):
        if not all([user_id, school_id, role]):
            return False, "ID do usuário, ID da escola e função são obrigatórios."

        user = db.session.get(User, user_id)
        school = db.session.get(School, school_id)

        if not user or not school:
            return False, "Usuário ou escola não encontrados."

        if (user.username or '') in ['super_admin', 'programador'] or user.role in ['super_admin', 'programador']:
            return False, f"Não é permitido alterar a função ou vincular o usuário privilegiado."

        user.role = role

        existing_assignment = db.session.execute(
            select(UserSchool).filter_by(user_id=user_id, school_id=school_id)
        ).scalar_one_or_none()

        if existing_assignment:
            existing_assignment.role = role
        else:
            new_assignment = UserSchool(user_id=user_id, school_id=school_id, role=role)
            db.session.add(new_assignment)

        try:
            db.session.commit()
            return True, f"Função de '{role}' atribuída com sucesso a {user.nome_completo or user.matricula} na escola {school.nome}."
        except IntegrityError:
            db.session.rollback()
            return False, "Ocorreu um erro de integridade. A atribuição pode já existir."

    @staticmethod
    def remove_school_role(user_id, school_id):
        if not user_id or not school_id:
            return False, "ID do usuário e ID da escola são obrigatórios."

        user = db.session.get(User, user_id)
        if user and ((user.username or '') in ['super_admin', 'programador'] or user.role in ['super_admin', 'programador']):
            return False, f"Não é permitido remover o vínculo escolar de um usuário privilegiado."

        assignment = db.session.execute(
            select(UserSchool).filter_by(user_id=user_id, school_id=school_id)
        ).scalar_one_or_none()

        if not assignment:
            return False, "Vínculo não encontrado para este usuário e escola."

        db.session.delete(assignment)
        db.session.commit()
        return True, "Vínculo com a escola removido com sucesso."

    @staticmethod
    def get_current_school_id():
        if not current_user.is_authenticated:
            return None

        if current_user.role in ['super_admin', 'programador']:
            school_id_from_session = session.get('view_as_school_id')
            if school_id_from_session:
                return school_id_from_session

        user_school = db.session.scalar(
            select(UserSchool).filter_by(user_id=current_user.id)
        )

        return user_school.school_id if user_school else None

    @staticmethod
    def delete_user_by_id(user_id: int):
        user = db.session.get(User, user_id)
        if not user:
            return False, "Usuário não encontrado."

        if user.role in ['super_admin', 'programador'] or (user.username or '') in ['super_admin', 'programador']:
            return False, "Não é permitido excluir um Super Admin ou Programador."

        try:
            db.session.delete(user)
            db.session.commit()
            return True, f"Usuário '{user.nome_completo or user.matricula}' foi excluído permanentemente."
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao excluir usuário: {e}")
            return False, "Ocorreu um erro interno ao tentar excluir o usuário."
