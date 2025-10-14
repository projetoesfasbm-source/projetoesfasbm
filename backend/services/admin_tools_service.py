# backend/services/admin_tools_service.py

from flask import current_app
from sqlalchemy import select, delete

from ..models.database import db
from ..models.user import User
from ..models.user_school import UserSchool
from ..models.disciplina import Disciplina

class AdminToolsService:
    @staticmethod
    def clear_students(school_id: int):
        """
        Exclui permanentemente todos os usuários com a função 'aluno'
        associados a uma escola específica.
        """
        try:
            # Encontra os IDs dos usuários que são alunos da escola especificada
            student_user_ids_query = (
                select(User.id)
                .join(UserSchool)
                .where(
                    User.role == 'aluno',
                    UserSchool.school_id == school_id
                )
            )
            student_user_ids = db.session.scalars(student_user_ids_query).all()

            if not student_user_ids:
                return True, "Nenhum aluno encontrado para excluir."

            # A exclusão do usuário em cascata removerá o perfil do aluno,
            # o vínculo user_school e outros dados relacionados.
            stmt = delete(User).where(User.id.in_(student_user_ids))
            result = db.session.execute(stmt)
            
            db.session.commit()
            return True, f"{result.rowcount} aluno(s) foram excluídos com sucesso."
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao limpar alunos: {e}")
            return False, "Ocorreu um erro ao tentar excluir os alunos."

    @staticmethod
    def clear_instructors(school_id: int):
        """
        Exclui permanentemente todos os usuários com a função 'instrutor'
        associados a uma escola específica.
        """
        try:
            instructor_user_ids_query = (
                select(User.id)
                .join(UserSchool)
                .where(
                    User.role == 'instrutor',
                    UserSchool.school_id == school_id
                )
            )
            instructor_user_ids = db.session.scalars(instructor_user_ids_query).all()

            if not instructor_user_ids:
                return True, "Nenhum instrutor encontrado para excluir."

            stmt = delete(User).where(User.id.in_(instructor_user_ids))
            result = db.session.execute(stmt)
            
            db.session.commit()
            return True, f"{result.rowcount} instrutor(es) foram excluídos com sucesso."
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao limpar instrutores: {e}")
            return False, "Ocorreu um erro ao tentar excluir os instrutores."

    @staticmethod
    def clear_disciplines(school_id: int):
        """
        Exclui permanentemente todas as disciplinas de uma escola.
        Os dados em cascata (horários, vínculos, histórico) serão removidos.
        """
        try:
            stmt = delete(Disciplina).where(Disciplina.school_id == school_id)
            result = db.session.execute(stmt)
            
            db.session.commit()
            return True, f"{result.rowcount} disciplina(s) foram excluídas com sucesso."
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao limpar disciplinas: {e}")
            return False, "Ocorreu um erro ao tentar excluir as disciplinas."