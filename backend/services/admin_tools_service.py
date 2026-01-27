# backend/services/admin_tools_service.py

from flask import current_app
from sqlalchemy import select

from ..models.database import db
from ..models.user import User
from ..models.user_school import UserSchool
from ..models.disciplina import Disciplina
from ..models.turma import Turma

class AdminToolsService:
    @staticmethod
    def clear_students(school_id: int):
        """
        Exclui permanentemente todos os usuários com a função 'aluno'
        associados a uma escola específica.
        Usa o ORM para garantir que a cascata (exclusão de perfil, notas, histórico) funcione.
        """
        try:
            # Busca os objetos User completos
            # ANEXADO: User.id == UserSchool.user_id no join para resolver ambiguidade Mapper
            students = db.session.scalars(
                select(User)
                .join(UserSchool, User.id == UserSchool.user_id)
                .where(
                    User.role == 'aluno',
                    UserSchool.school_id == school_id
                )
            ).all()

            if not students:
                return True, "Nenhum aluno encontrado para excluir."

            count = len(students)
            # Deleta um por um para ativar o 'cascade="all, delete-orphan"' do modelo SQLAlchemy
            for student in students:
                db.session.delete(student)
            
            db.session.commit()
            return True, f"{count} aluno(s) foram excluídos com sucesso."
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao limpar alunos: {e}")
            return False, f"Ocorreu um erro ao tentar excluir os alunos: {str(e)}"

    @staticmethod
    def clear_instructors(school_id: int):
        """
        Exclui permanentemente todos os usuários com a função 'instrutor'
        associados a uma escola específica.
        """
        try:
            # ANEXADO: User.id == UserSchool.user_id no join para resolver ambiguidade Mapper
            instructors = db.session.scalars(
                select(User)
                .join(UserSchool, User.id == UserSchool.user_id)
                .where(
                    User.role == 'instrutor',
                    UserSchool.school_id == school_id
                )
            ).all()

            if not instructors:
                return True, "Nenhum instrutor encontrado para excluir."

            count = len(instructors)
            for instructor in instructors:
                db.session.delete(instructor)
            
            db.session.commit()
            return True, f"{count} instrutor(es) foram excluídos com sucesso."
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao limpar instrutores: {e}")
            return False, f"Ocorreu um erro ao tentar excluir os instrutores: {str(e)}"

    @staticmethod
    def clear_disciplines(school_id: int):
        """
        Exclui permanentemente todas as disciplinas de uma escola,
        navegando através das turmas.
        """
        try:
            # Busca disciplinas através das turmas da escola
            # Também usamos o ORM aqui para garantir que Horários e Históricos sejam limpos
            # ANEXADO: Disciplina.turma_id == Turma.id no join para segurança
            disciplines = db.session.scalars(
                select(Disciplina)
                .join(Turma, Disciplina.turma_id == Turma.id)
                .where(Turma.school_id == school_id)
            ).all()

            if not disciplines:
                return True, "Nenhuma disciplina encontrada para excluir."

            count = len(disciplines)
            for discipline in disciplines:
                db.session.delete(discipline)
            
            db.session.commit()
            return True, f"{count} disciplina(s) foram excluídas com sucesso."
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao limpar disciplinas: {e}")
            return False, f"Ocorreu um erro ao tentar excluir as disciplinas: {str(e)}"