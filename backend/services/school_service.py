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
            
            # Recuperar IDs das turmas para limpar dependências
            turmas_ids = db.session.scalars(select(Turma.id).where(Turma.school_id == school_id)).all()
            
            if turmas_ids:
                # 1.1 Excluir Diários de Classe ligados às turmas dessa escola
                db.session.query(DiarioClasse).filter(DiarioClasse.turma_id.in_(turmas_ids)).delete(synchronize_session=False)

                # 1.2 Excluir Horários (via Semanas)
                semanas_ids = db.session.scalars(select(Semana.id).where(Semana.turma_id.in_(turmas_ids))).all()
                if semanas_ids:
                    db.session.query(Horario).filter(Horario.semana_id.in_(semanas_ids)).delete(synchronize_session=False)

                # 1.3 Limpar dados vinculados aos Alunos dessas turmas (Processos e Avaliações)
                alunos_ids = db.session.scalars(select(Aluno.id).where(Aluno.turma_id.in_(turmas_ids))).all()
                if alunos_ids:
                    # Processos onde o aluno é o réu
                    db.session.query(ProcessoDisciplina).filter(ProcessoDisciplina.aluno_id.in_(alunos_ids)).delete(synchronize_session=False)
                    # Avaliações FADA recebidas pelo aluno
                    db.session.query(FadaAvaliacao).filter(FadaAvaliacao.aluno_id.in_(alunos_ids)).delete(synchronize_session=False)

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
                    if user and user.role not in ['super_admin', 'programador']:
                        users_to_delete.append(user)

            # === FASE 3: Excluir a Escola ===
            # Agora que limpamos diários e processos de alunos, a escola (e turmas) pode ser excluída
            db.session.delete(school)
            db.session.flush() # Aplica para remover UserSchool pelo cascade

            # === FASE 4: Limpar e Excluir Usuários Órfãos (Instrutores/Admins) ===
            count_deleted = 0
            
            with db.session.no_autoflush:
                for user in users_to_delete:
                    # A. Limpar Avaliações FADA (onde usuário é Avaliador)
                    db.session.query(FadaAvaliacao).filter(FadaAvaliacao.avaliador_id == user.id).delete()
                    
                    # B. Limpar Processos Disciplinares (onde usuário é Relator)
                    db.session.query(ProcessoDisciplina).filter(ProcessoDisciplina.relator_id == user.id).delete()

                    # C. Limpar Respostas de Questionários (onde usuário respondeu)
                    db.session.query(Resposta).filter(Resposta.user_id == user.id).delete()
                    
                    # D. Limpar Diários de Classe (onde usuário é Responsável - caso tenha sobrado de outras escolas bugadas ou orfãs)
                    db.session.query(DiarioClasse).filter(DiarioClasse.responsavel_id == user.id).delete()

                    # E. Excluir o Usuário
                    db.session.delete(user)
                    count_deleted += 1

            db.session.commit()
            return True, f"Escola '{school_name}' excluída com sucesso. {count_deleted} usuários exclusivos foram removidos e seus vínculos limpos."

        except Exception as e:
            db.session.rollback()
            return False, f"Erro crítico ao excluir dados: {str(e)}"