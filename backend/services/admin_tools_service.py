# backend/services/admin_tools_service.py

from flask import current_app
from sqlalchemy import select
from datetime import datetime, date, time

from ..models.database import db
from ..models.user import User
from ..models.user_school import UserSchool
from ..models.disciplina import Disciplina
from ..models.disciplina_turma import DisciplinaTurma
from ..models.turma import Turma
from ..models.ciclo import Ciclo

class AdminToolsService:
    
    @staticmethod
    def generate_school_backup(school_id: int) -> dict:
        """
        Coleta TODOS os dados da escola/edição atual e os estrutura num dicionário
        que será exportado como um snapshot JSON.
        Os dados sensíveis (senhas e tokens) são removidos ativamente na serialização.
        Injeta os nomes reais para evitar problemas de undefined no front-end.
        """
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
            """Converte as colunas de um objeto SQLAlchemy num dicionário limpo e higienizado."""
            if not obj:
                return None
            data = {}
            
            # BLOQUEIO DE SEGURANÇA: Colunas que NUNCA devem ir para o JSON de backup
            EXCLUDE = ['password_hash', 'reset_token', 'reset_token_expiration']
            
            for col in obj.__table__.columns:
                if col.name in EXCLUDE:
                    continue # Pula a coluna censurada
                    
                val = getattr(obj, col.name)
                
                if isinstance(val, (datetime, date, time)):
                    data[col.name] = val.isoformat()
                else:
                    data[col.name] = val
            return data

        # Dicionários de busca rápida para o backend
        users_cache = {}
        turmas_cache = {}
        disciplinas_cache = {}
        vinculos_cache = {}

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
            "disciplinas": [], # Disciplinas Globais
            "vinculos_disciplinas": [], # DisciplinaTurma
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
            for t in turmas_db:
                backup["turmas"].append(serialize_model(t))
                turmas_cache[t.id] = t.nome
            turma_ids = [t.id for t in turmas_db] if turmas_db else []

            # 3. Usuários
            users_db = db.session.scalars(
                select(User).join(UserSchool).where(UserSchool.school_id == school_id)
            ).all()
            for u in users_db:
                backup["usuarios"].append(serialize_model(u))
                users_cache[u.id] = {
                    "nome": u.nome_completo or u.nome_de_guerra or u.username or "Sem Nome",
                    "matricula": u.matricula or "Não informada"
                }
            user_ids = [u.id for u in users_db] if users_db else []

            # 4. Disciplinas Globais e Vínculos
            if turma_ids:
                # CORREÇÃO: Disciplina se liga à Turma diretamente. DisciplinaTurma liga Disciplina ao Instrutor.
                disciplinas_db = db.session.scalars(
                    select(Disciplina).where(Disciplina.turma_id.in_(turma_ids))
                ).all()
                
                disc_ids = set()
                for d in disciplinas_db:
                    backup["disciplinas"].append(serialize_model(d))
                    disciplinas_cache[d.id] = d.materia
                    disc_ids.add(d.id)
                
                if disc_ids:
                    vinculos_db = db.session.scalars(
                        select(DisciplinaTurma).where(DisciplinaTurma.disciplina_id.in_(list(disc_ids)))
                    ).all()
                    for v in vinculos_db:
                        backup["vinculos_disciplinas"].append(serialize_model(v))

            # Função auxiliar para resolver nome da disciplina
            def resolve_disciplina_nome(disc_id):
                return disciplinas_cache.get(disc_id, "Desconhecida")

            # 5. Ciclos
            ciclos_db = db.session.scalars(select(Ciclo).where(Ciclo.school_id == school_id)).all()
            backup["ciclos"] = [serialize_model(c) for c in ciclos_db]
            ciclo_ids = [c.id for c in ciclos_db] if ciclos_db else []

            # 6. Semanas
            if ciclo_ids:
                semanas_db = db.session.scalars(
                    select(Semana).where(Semana.ciclo_id.in_(ciclo_ids))
                ).all()
                backup["semanas"] = [serialize_model(s) for s in semanas_db]
                semana_ids = [s.id for s in semanas_db] if semanas_db else []

                # 7. Horarios
                if semana_ids:
                    horarios_db = db.session.scalars(
                        select(Horario).where(Horario.semana_id.in_(semana_ids))
                    ).all()
                    backup["horarios"] = [serialize_model(h) for h in horarios_db]

            # 8. Diarios
            diario_ids = []
            if turma_ids:
                diarios_db = db.session.scalars(
                    select(DiarioClasse).where(DiarioClasse.turma_id.in_(turma_ids))
                ).all()
                for d in diarios_db:
                    d_data = serialize_model(d)
                    d_data["injected_turma_nome"] = turmas_cache.get(d.turma_id, "Desconhecida")
                    d_data["injected_disciplina_nome"] = resolve_disciplina_nome(d.disciplina_id)
                    backup["diarios_classe"].append(d_data)
                    diario_ids.append(d.id)

            # 9. Frequencias
            if diario_ids:
                frequencias_db = db.session.scalars(
                    select(FrequenciaAluno).where(FrequenciaAluno.diario_id.in_(diario_ids))
                ).all()
                for f in frequencias_db:
                    f_data = serialize_model(f)
                    user_info = users_cache.get(f.aluno_id, {})
                    f_data["injected_aluno_nome"] = user_info.get("nome", "Desconhecido")
                    f_data["injected_aluno_matricula"] = user_info.get("matricula", "N/A")
                    backup["frequencias"].append(f_data)

            # 10. Historico e Justica (INJEÇÃO COMPLETA DE PROCESSOS)
            if user_ids:
                historicos_db = db.session.scalars(
                    select(HistoricoAluno).where(HistoricoAluno.aluno_id.in_(user_ids))
                ).all()
                backup["historicos"] = [serialize_model(h) for h in historicos_db]

                # Processos Disciplinares com todos os detalhes de texto
                processos_db = db.session.scalars(
                    select(ProcessoDisciplina).where(ProcessoDisciplina.aluno_id.in_(user_ids))
                ).all()
                for p in processos_db:
                    p_data = serialize_model(p)
                    user_info = users_cache.get(p.aluno_id, {})
                    p_data["injected_aluno_nome"] = user_info.get("nome", "Desconhecido")
                    p_data["injected_aluno_matricula"] = user_info.get("matricula", "N/A")
                    
                    # Relator
                    relator_info = users_cache.get(p.relator_id, {})
                    p_data["injected_relator_nome"] = relator_info.get("nome", "N/A")
                    
                    backup["justica"]["processos"].append(p_data)

                # Elogios
                elogios_db = db.session.scalars(
                    select(Elogio).where(Elogio.aluno_id.in_(user_ids))
                ).all()
                for e in elogios_db:
                    e_data = serialize_model(e)
                    user_info = users_cache.get(e.aluno_id, {})
                    e_data["injected_aluno_nome"] = user_info.get("nome", "Desconhecido")
                    e_data["injected_aluno_matricula"] = user_info.get("matricula", "N/A")
                    backup["justica"]["elogios"].append(e_data)

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