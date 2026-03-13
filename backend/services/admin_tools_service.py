# backend/services/admin_tools_service.py

from flask import current_app
from sqlalchemy import select
from datetime import datetime, date, time

from ..models.database import db
from ..models.user import User
from ..models.user_school import UserSchool
from ..models.disciplina import Disciplina
from ..models.turma import Turma
from ..models.ciclo import Ciclo

class AdminToolsService:
    
    @staticmethod
    def generate_school_backup(school_id: int) -> dict:
        """
        Coleta TODOS os dados da escola/edição atual e os estrutura num dicionário
        que será exportado como um snapshot JSON.
        """
        # Imports locais para evitar problemas de dependência circular
        from ..models.school import School
        from ..models.semana import Semana
        from ..models.horario import Horario
        from ..models.diario_classe import DiarioClasse
        from ..models.frequencia import FrequenciaAluno
        from ..models.historico import HistoricoAluno
        from ..models.processo_disciplina import ProcessoDisciplina
        from ..models.elogio import Elogio
        from ..models.fada_avaliacao import FadaAvaliacao

        def serialize_model(obj):
            """Converte as colunas de um objeto SQLAlchemy num dicionário limpo."""
            if not obj:
                return None
            data = {}
            for col in obj.__table__.columns:
                val = getattr(obj, col.name)
                # Converte tipos de tempo para string ISO, para não quebrar a geração do JSON
                if isinstance(val, (datetime, date, time)):
                    data[col.name] = val.isoformat()
                else:
                    data[col.name] = val
            return data

        backup = {
            "meta": {
                "generated_at": datetime.now().isoformat(),
                "school_id": school_id
            },
            "escola": {},
            "turmas": [],
            "ciclos": [],
            "semanas": [],
            "horarios": [],
            "usuarios": [],
            "disciplinas": [],
            "diarios_classe": [],
            "frequencias": [],
            "historicos": [],
            "justica": {
                "processos": [],
                "elogios": [],
                "fadas": []
            }
        }

        try:
            # 1. Escola
            school_db = db.session.get(School, school_id)
            if school_db:
                backup["escola"] = serialize_model(school_db)

            # 2. Turmas
            turmas_db = db.session.scalars(select(Turma).where(Turma.school_id == school_id)).all()
            backup["turmas"] = [serialize_model(t) for t in turmas_db]
            turma_ids = [t.id for t in turmas_db] if turmas_db else []

            # 3. Usuários (Todos vinculados a esta escola: alunos, instrutores, coordenação)
            users_db = db.session.scalars(
                select(User).join(UserSchool).where(UserSchool.school_id == school_id)
            ).all()
            backup["usuarios"] = [serialize_model(u) for u in users_db]
            user_ids = [u.id for u in users_db] if users_db else []

            # 4. Disciplinas (Buscando através das turmas da escola)
            if turma_ids:
                disciplinas_db = db.session.scalars(
                    select(Disciplina).where(Disciplina.turma_id.in_(turma_ids))
                ).all()
                backup["disciplinas"] = [serialize_model(d) for d in disciplinas_db]
                
            # 5. Ciclos (A base para encontrar as Semanas de Horários da Escola)
            ciclos_db = db.session.scalars(select(Ciclo).where(Ciclo.school_id == school_id)).all()
            backup["ciclos"] = [serialize_model(c) for c in ciclos_db]
            ciclo_ids = [c.id for c in ciclos_db] if ciclos_db else []

            # 6. Semanas do Quadro Horário (Buscando através dos Ciclos da Escola)
            if ciclo_ids:
                semanas_db = db.session.scalars(
                    select(Semana).where(Semana.ciclo_id.in_(ciclo_ids))
                ).all()
                backup["semanas"] = [serialize_model(s) for s in semanas_db]
                semana_ids = [s.id for s in semanas_db] if semanas_db else []

                # 7. Horários das Aulas
                if semana_ids:
                    horarios_db = db.session.scalars(
                        select(Horario).where(Horario.semana_id.in_(semana_ids))
                    ).all()
                    backup["horarios"] = [serialize_model(h) for h in horarios_db]
                    horario_ids = [h.id for h in horarios_db] if horarios_db else []

                    # 8. Diários de Classe (Assinaturas dos Instrutores)
                    if horario_ids:
                        diarios_db = db.session.scalars(
                            select(DiarioClasse).where(DiarioClasse.horario_id.in_(horario_ids))
                        ).all()
                        backup["diarios_classe"] = [serialize_model(d) for d in diarios_db]
                        diario_ids = [d.id for d in diarios_db] if diarios_db else []

                        # 9. Frequências (Faltas dos alunos naqueles diários)
                        if diario_ids:
                            frequencias_db = db.session.scalars(
                                select(FrequenciaAluno).where(FrequenciaAluno.diario_id.in_(diario_ids))
                            ).all()
                            backup["frequencias"] = [serialize_model(f) for f in frequencias_db]

            # 10. Dados Individuais (Histórico de Notas e Registros de Justiça)
            if user_ids:
                historicos_db = db.session.scalars(
                    select(HistoricoAluno).where(HistoricoAluno.aluno_id.in_(user_ids))
                ).all()
                backup["historicos"] = [serialize_model(h) for h in historicos_db]

                processos_db = db.session.scalars(
                    select(ProcessoDisciplina).where(ProcessoDisciplina.aluno_id.in_(user_ids))
                ).all()
                backup["justica"]["processos"] = [serialize_model(p) for p in processos_db]

                elogios_db = db.session.scalars(
                    select(Elogio).where(Elogio.aluno_id.in_(user_ids))
                ).all()
                backup["justica"]["elogios"] = [serialize_model(e) for e in elogios_db]

                fadas_db = db.session.scalars(
                    select(FadaAvaliacao).where(FadaAvaliacao.aluno_id.in_(user_ids))
                ).all()
                backup["justica"]["fadas"] = [serialize_model(f) for f in fadas_db]

            return backup

        except Exception as e:
            current_app.logger.error(f"Falha ao gerar backup completo da escola {school_id}: {e}")
            raise e

    @staticmethod
    def clear_students(school_id: int):
        """
        Exclui permanentemente todos os usuários com a função 'aluno'
        associados a uma escola específica.
        Usa o ORM para garantir que a cascata (exclusão de perfil, notas, histórico) funcione.
        """
        try:
            # Busca os objetos User completos
            students = db.session.scalars(
                select(User)
                .join(UserSchool)
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
            instructors = db.session.scalars(
                select(User)
                .join(UserSchool)
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
            disciplines = db.session.scalars(
                select(Disciplina)
                .join(Turma)
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