from ..models.database import db
from ..models.school import School
from sqlalchemy.exc import IntegrityError

class SchoolService:
    @staticmethod
    def create_school(name: str):
        """Cria uma nova escola."""
        if not name:
            return False, "O nome da escola não pode estar vazio."

        try:
            new_school = School(nome=name)
            db.session.add(new_school)
            db.session.commit()
            return True, f"Escola '{name}' criada com sucesso."
        except IntegrityError:
            db.session.rollback()
            return False, f"Uma escola com o nome '{name}' já existe."
        except Exception as e:
            db.session.rollback()
            return False, f"Ocorreu um erro inesperado: {e}"

    @staticmethod
    def delete_school(school_id: int):
        """Exclui uma escola e todos os seus vínculos."""
        school = db.session.get(School, school_id)
        if not school:
            return False, "Escola não encontrada."
        
        try:
            # A configuração 'cascade="all, delete-orphan"' nos relacionamentos
            # (user_schools, turmas, disciplinas) irá remover automaticamente
            # todos os registos associados.
            db.session.delete(school)
            db.session.commit()
            return True, f"Escola '{school.nome}' e todos os seus dados associados foram excluídos com sucesso."
        except Exception as e:
            db.session.rollback()
            return False, f"Ocorreu um erro ao excluir a escola: {e}"