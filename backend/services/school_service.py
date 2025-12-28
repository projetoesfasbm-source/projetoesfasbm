# backend/services/school_service.py

from ..models.database import db
from ..models.school import School
from ..models.user import User
from ..models.user_school import UserSchool
from ..models.fada_avaliacao import FadaAvaliacao  # Importação necessária para a limpeza
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, func

class SchoolService:
    @staticmethod
    def create_school(name: str, npccal_type: str):
        """Cria uma nova escola."""
        if not name:
            return False, "O nome da escola não pode estar vazio."
            
        if not npccal_type:
            return False, "O Tipo de NPCCAL é obrigatório."

        try:
            new_school = School(nome=name, npccal_type=npccal_type)
            db.session.add(new_school)
            db.session.commit()
            return True, f"Escola '{name}' (Tipo: {npccal_type.upper()}) criada com sucesso."
        except IntegrityError:
            db.session.rollback()
            return False, f"Uma escola com o nome '{name}' já existe."
        except Exception as e:
            db.session.rollback()
            return False, f"Ocorreu um erro inesperado: {e}"

    @staticmethod
    def update_school(school_id: int, name: str, npccal_type: str):
        """Atualiza os dados de uma escola existente."""
        school = db.session.get(School, school_id)
        if not school:
            return False, "Escola não encontrada."
            
        if not name:
            return False, "O nome da escola não pode estar vazio."
            
        if not npccal_type:
            return False, "O Tipo de NPCCAL é obrigatório."

        try:
            school.nome = name
            school.npccal_type = npccal_type
            db.session.commit()
            return True, f"Escola '{name}' atualizada com sucesso."
        except IntegrityError:
            db.session.rollback()
            return False, f"Já existe outra escola com o nome '{name}'."
        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao atualizar escola: {e}"

    @staticmethod
    def delete_school(school_id: int, current_user, password: str):
        """
        Exclui uma escola e TODOS os dados associados (usuários exclusivos e históricos).
        Requer confirmação de senha por segurança.
        """
        # 1. Validação de Segurança
        if not current_user.check_password(password):
             return False, "Senha incorreta. A exclusão não foi realizada."

        school = db.session.get(School, school_id)
        if not school:
            return False, "Escola não encontrada."
        
        school_name = school.nome

        try:
            # 2. Identificar usuários que pertencem APENAS a esta escola (Exclusivos)
            linked_user_ids = db.session.scalars(
                select(UserSchool.user_id).where(UserSchool.school_id == school_id)
            ).all()

            users_to_delete = []
            for uid in linked_user_ids:
                # Verifica contagem de vínculos
                count_links = db.session.scalar(
                    select(func.count(UserSchool.id)).where(UserSchool.user_id == uid)
                )
                if count_links == 1:
                    user = db.session.get(User, uid)
                    # Proteção: não excluir super admins ou programadores automaticamente
                    if user and user.role not in ['super_admin', 'programador']:
                        users_to_delete.append(user)

            # 3. Remover a Escola
            # O cascade 'delete-orphan' na School remove os vínculos em UserSchool imediatamente
            db.session.delete(school)
            db.session.flush() # Aplica no banco (sem commitar) para liberar os vínculos

            # 4. Limpar e Excluir Usuários Órfãos
            count_deleted = 0
            for user in users_to_delete:
                # A. Remover Avaliações FADA onde o usuário é o AVALIADOR
                # Isso corrige o erro de Foreign Key (Constraint fails)
                db.session.query(FadaAvaliacao).filter(FadaAvaliacao.avaliador_id == user.id).delete()

                # B. Remover Avaliações FADA onde o usuário é o ALUNO (via perfil de aluno)
                if user.aluno_profile:
                    db.session.query(FadaAvaliacao).filter(FadaAvaliacao.aluno_id == user.aluno_profile.id).delete()

                # C. Excluir o Usuário
                db.session.delete(user)
                count_deleted += 1

            db.session.commit()
            return True, f"Escola '{school_name}' excluída com sucesso. {count_deleted} usuários exclusivos e seus históricos foram removidos."

        except Exception as e:
            db.session.rollback()
            return False, f"Erro crítico ao excluir dados: {str(e)}"