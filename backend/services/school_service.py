# backend/services/school_service.py

from ..models.database import db
from ..models.school import School
from ..models.user import User
from ..models.user_school import UserSchool
from ..models.turma import Turma
from ..models.semana import Semana
from ..models.aluno import Aluno
from ..models.fada_avaliacao import FadaAvaliacao
from ..models.processo_disciplina import ProcessoDisciplina
from ..models.diario_classe import DiarioClasse
from ..models.horario import Horario
from ..models.resposta import Resposta
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, func

class SchoolService:
    @staticmethod
    def create_school(name: str, admin_id: int = None):
        """Cria uma nova escola e opcionalmente associa um administrador."""
        if not name:
            return False, "O nome da escola não pode estar vazio."

        try:
            new_school = School(nome=name)
            db.session.add(new_school)
            db.session.flush() # Gera o ID da nova escola

            if admin_id:
                admin_user = db.session.get(User, admin_id)
                if not admin_user:
                    db.session.rollback()
                    return False, "Administrador selecionado não encontrado."
                
                # Criar o vínculo do administrador com a nova escola
                user_school = UserSchool(
                    user_id=admin_id,
                    school_id=new_school.id,
                    role='admin_escola'
                )
                db.session.add(user_school)

            db.session.commit()
            return True, f"Escola '{name}' criada com sucesso e administrador associado."
        except IntegrityError:
            db.session.rollback()
            return False, f"Uma escola com o nome '{name}' já existe."
        except Exception as e:
            db.session.rollback()
            return False, f"Ocorreu um erro inesperado: {e}"

    @staticmethod
    def update_school(school_id: int, name: str):
        """Atualiza os dados de uma escola existente."""
        school = db.session.get(School, school_id)
        if not school:
            return False, "Escola não encontrada."
            
        if not name:
            return False, "O nome da escola não pode estar vazio."

        try:
            school.nome = name
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
        Exclui uma escola e TODOS os dados associados.
        Realiza limpeza profunda de dependências (Diários, Horários, Processos, Respostas)
        para evitar erros de chave estrangeira (IntegrityError).
        """
        # 1. Validação de Segurança
        if not current_user.check_password(password):
             return False, "Senha incorreta. A exclusão não foi realizada."

        school = db.session.get(School, school_id)
        if not school:
            return False, "Escola não encontrada."
        
        school_name = school.nome

        try:
            # === FASE 1: Limpeza de dados da ESCOLA (Desbloqueia exclusão de Turmas e Alunos) ===
            
            turmas_ids = db.session.scalars(select(Turma.id).where(Turma.school_id == school_id)).all()
            
            def chunked_delete(model, column, values, chunk_size=500):
                for i in range(0, len(values), chunk_size):
                    chunk = values[i:i+chunk_size]
                    db.session.execute(model.__table__.delete().where(column.in_(chunk)))
                db.session.flush()

            if turmas_ids:
                # 1.1 Excluir Diários de Classe ligados às turmas dessa escola
                chunked_delete(DiarioClasse, DiarioClasse.turma_id, turmas_ids)

                # 1.2 Excluir Horários (via Semanas)
                semanas_ids = db.session.scalars(select(Semana.id).where(Semana.turma_id.in_(turmas_ids))).all()
                if semanas_ids:
                    chunked_delete(Horario, Horario.semana_id, semanas_ids)

                # 1.3 Limpar dados vinculados aos Alunos dessas turmas (Processos e Avaliações)
                alunos_ids = db.session.scalars(select(Aluno.id).where(Aluno.turma_id.in_(turmas_ids))).all()
                if alunos_ids:
                    # Processos onde o aluno é o réu
                    chunked_delete(ProcessoDisciplina, ProcessoDisciplina.aluno_id, alunos_ids)
                    # Avaliações FADA recebidas pelo aluno
                    chunked_delete(FadaAvaliacao, FadaAvaliacao.aluno_id, alunos_ids)

            # === FASE 2: Identificar Usuários Exclusivos ===
            linked_user_ids = db.session.scalars(
                select(UserSchool.user_id).where(UserSchool.school_id == school_id)
            ).all()

            users_to_delete = []
            for uid in linked_user_ids:
                count_links = db.session.scalar(
                    select(func.count(UserSchool.id)).where(UserSchool.user_id == uid)
                )
                if count_links == 1:
                    user = db.session.get(User, uid)
                    if user and user.role != 'super_admin':
                        users_to_delete.append(user)

            # === FASE 3: Excluir a Escola ===
            # Agora que limpamos diários e processos de alunos, a escola (e turmas) pode ser excluída
            db.session.delete(school)
            db.session.flush() # Aplica para remover UserSchool pelo cascade

            # === FASE 4: Limpar e Excluir Usuários Órfãos (Instrutores/Admins) ===
            count_deleted = 0
            
            user_ids_to_delete = [u.id for u in users_to_delete]
            if user_ids_to_delete:
                chunked_delete(FadaAvaliacao, FadaAvaliacao.avaliador_id, user_ids_to_delete)
                chunked_delete(ProcessoDisciplina, ProcessoDisciplina.relator_id, user_ids_to_delete)
                chunked_delete(Resposta, Resposta.user_id, user_ids_to_delete)
                chunked_delete(DiarioClasse, DiarioClasse.responsavel_id, user_ids_to_delete)
                
                with db.session.no_autoflush:
                    for user in users_to_delete:
                        db.session.delete(user)
                        count_deleted += 1

            db.session.commit()
            return True, f"Escola '{school_name}' excluída com sucesso. {count_deleted} usuários exclusivos foram removidos e seus vínculos limpos."

        except Exception as e:
            db.session.rollback()
            return False, f"Erro crítico ao excluir dados: {str(e)}"