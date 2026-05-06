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
from ..models.semana import Semana
from ..models.horario import Horario
from ..models.diario_classe import DiarioClasse
from ..models.frequencia import FrequenciaAluno
from ..models.turma_cargo import TurmaCargo
from ..models.questionario import Questionario
from ..models.pergunta import Pergunta
from ..models.resposta import Resposta
from ..models.banco_questoes import QuestaoBanco, RascunhoProva, DelegacaoProva
from ..models.elogio import Elogio
from ..models.fada_avaliacao import FadaAvaliacao
from ..models.processo_disciplina import ProcessoDisciplina
from ..models.avaliacao import AvaliacaoAtitudinal
from ..models.historico import HistoricoAluno
from ..models.historico_disciplina import HistoricoDisciplina
from ..models.notification import Notification
from ..models.password_reset_token import PasswordResetToken
from ..models.push_subscription import PushSubscription
from ..models.aluno import Aluno
from ..models.instrutor import Instrutor

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

                processos_db = db.session.scalars(
                    select(ProcessoDisciplina).where(ProcessoDisciplina.aluno_id.in_(user_ids))
                ).all()
                for p in processos_db:
                    p_data = serialize_model(p)
                    user_info = users_cache.get(p.aluno_id, {})
                    p_data["injected_aluno_nome"] = user_info.get("nome", "Desconhecido")
                    p_data["injected_aluno_matricula"] = user_info.get("matricula", "N/A")
                    
                    relator_info = users_cache.get(p.relator_id, {})
                    p_data["injected_relator_nome"] = relator_info.get("nome", "N/A")
                    
                    backup["justica"]["processos"].append(p_data)

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
    def custom_clear_school_data(school_id: int, options: list, instructors_to_delete_ids: list = None):
        """
        Processa as opções selecionadas via checkbox e as limpa em lote, lidando 
        com as dependências do banco ativamente para evitar erros de Integridade Referencial.
        Recebe opcionalmente uma lista refinada de instrutores para desvincular da escola atual.
        """
        try:
            if 'turmas' in options:
                options.extend(['disciplinas', 'diarios', 'questionarios', 'vinculos'])
            if 'disciplinas' in options:
                options.extend(['diarios', 'vinculos'])
            if 'ciclos' in options:
                options.extend(['semanas', 'horarios'])

            options = list(set(options)) # Remove duplicatas

            # 1. Coletar IDs Básicos de Usuário
            all_users = db.session.scalars(select(User).join(UserSchool).where(UserSchool.school_id == school_id)).all()
            student_ids = [u.id for u in all_users if u.role == 'aluno']
            
            # Se a lista de instrutores foi enviada pela tela de confirmação, usamos ela.
            if instructors_to_delete_ids is not None:
                instructor_ids = [u.id for u in all_users if u.role == 'instrutor' and u.id in instructors_to_delete_ids]
            else:
                instructor_ids = []

            alunos_db = db.session.scalars(select(Aluno).where(Aluno.user_id.in_(student_ids))).all() if student_ids else []
            aluno_ids = [a.id for a in alunos_db] if alunos_db else []

            turmas = db.session.scalars(select(Turma).where(Turma.school_id == school_id)).all()
            turma_ids = [t.id for t in turmas] if turmas else []

            ciclos = db.session.scalars(select(Ciclo).where(Ciclo.school_id == school_id)).all()
            ciclo_ids = [c.id for c in ciclos] if ciclos else []

            # LIMPEZA DAS DEPENDÊNCIAS MENORES (Cascata Forçada) ==================

            # Justiça
            if 'justica' in options and aluno_ids:
                db.session.query(ProcessoDisciplina).filter(ProcessoDisciplina.aluno_id.in_(aluno_ids)).delete(synchronize_session=False)
                db.session.query(Elogio).filter(Elogio.aluno_id.in_(aluno_ids)).delete(synchronize_session=False)
                db.session.query(FadaAvaliacao).filter(FadaAvaliacao.aluno_id.in_(aluno_ids)).delete(synchronize_session=False)
                db.session.query(AvaliacaoAtitudinal).filter(AvaliacaoAtitudinal.aluno_id.in_(aluno_ids)).delete(synchronize_session=False)

            # Questionários (e respostas)
            if 'questionarios' in options and turma_ids:
                questoes = db.session.scalars(select(Questionario).where(Questionario.turma_id.in_(turma_ids))).all()
                for q in questoes:
                    db.session.query(Resposta).filter(Resposta.pergunta_id.in_(
                        select(Pergunta.id).where(Pergunta.questionario_id == q.id)
                    )).delete(synchronize_session=False)
                    db.session.delete(q)

            # Diários de Classe (e frequências)
            if 'diarios' in options and turma_ids:
                diarios = db.session.scalars(select(DiarioClasse).where(DiarioClasse.turma_id.in_(turma_ids))).all()
                diario_ids = [d.id for d in diarios] if diarios else []
                if diario_ids:
                    db.session.query(FrequenciaAluno).filter(FrequenciaAluno.diario_id.in_(diario_ids)).delete(synchronize_session=False)
                    db.session.query(DiarioClasse).filter(DiarioClasse.id.in_(diario_ids)).delete(synchronize_session=False)

            # Vínculos Disciplina-Instrutor
            if 'vinculos' in options and turma_ids:
                disciplinas = db.session.scalars(select(Disciplina).where(Disciplina.turma_id.in_(turma_ids))).all()
                disc_ids = [d.id for d in disciplinas] if disciplinas else []
                if disc_ids:
                    db.session.query(DisciplinaTurma).filter(DisciplinaTurma.disciplina_id.in_(disc_ids)).delete(synchronize_session=False)

            # Disciplinas (e horários, históricos)
            if 'disciplinas' in options and turma_ids:
                disciplinas = db.session.scalars(select(Disciplina).where(Disciplina.turma_id.in_(turma_ids))).all()
                disc_ids = [d.id for d in disciplinas] if disciplinas else []
                if disc_ids:
                    db.session.query(HistoricoDisciplina).filter(HistoricoDisciplina.disciplina_id.in_(disc_ids)).delete(synchronize_session=False)
                    db.session.query(Horario).filter(Horario.disciplina_id.in_(disc_ids)).delete(synchronize_session=False)
                    db.session.query(Disciplina).filter(Disciplina.id.in_(disc_ids)).delete(synchronize_session=False)

            # Ciclos (e semanas, horários)
            if 'ciclos' in options and ciclo_ids:
                semanas = db.session.scalars(select(Semana).where(Semana.ciclo_id.in_(ciclo_ids))).all()
                semana_ids = [s.id for s in semanas] if semanas else []
                if semana_ids:
                    db.session.query(Horario).filter(Horario.semana_id.in_(semana_ids)).delete(synchronize_session=False)
                    db.session.query(Semana).filter(Semana.id.in_(semana_ids)).delete(synchronize_session=False)
                db.session.query(Ciclo).filter(Ciclo.id.in_(ciclo_ids)).delete(synchronize_session=False)

            # Turmas
            if 'turmas' in options and turma_ids:
                db.session.query(TurmaCargo).filter(TurmaCargo.turma_id.in_(turma_ids)).delete(synchronize_session=False)
                db.session.query(Turma).filter(Turma.id.in_(turma_ids)).delete(synchronize_session=False)

            # LIMPEZA DE USUÁRIOS ==================================================
            
            # Alunos
            if 'alunos' in options and student_ids:
                if aluno_ids:
                    db.session.query(FrequenciaAluno).filter(FrequenciaAluno.aluno_id.in_(aluno_ids)).delete(synchronize_session=False)
                    db.session.query(HistoricoDisciplina).filter(HistoricoDisciplina.aluno_id.in_(aluno_ids)).delete(synchronize_session=False)
                    db.session.query(HistoricoAluno).filter(HistoricoAluno.aluno_id.in_(aluno_ids)).delete(synchronize_session=False)
                    db.session.query(ProcessoDisciplina).filter(ProcessoDisciplina.aluno_id.in_(aluno_ids)).delete(synchronize_session=False)
                    db.session.query(Elogio).filter(Elogio.aluno_id.in_(aluno_ids)).delete(synchronize_session=False)
                    db.session.query(FadaAvaliacao).filter(FadaAvaliacao.aluno_id.in_(aluno_ids)).delete(synchronize_session=False)
                    db.session.query(AvaliacaoAtitudinal).filter(AvaliacaoAtitudinal.aluno_id.in_(aluno_ids)).delete(synchronize_session=False)

                # --- LIMPEZA DE CARGOS E VÍNCULOS PERDIDOS DOS ALUNOS ---
                # Como o aluno pode ser Chefe de Turma, limpamos o TurmaCargo com segurança dinâmica
                if hasattr(TurmaCargo, 'aluno_id') and aluno_ids:
                    db.session.query(TurmaCargo).filter(TurmaCargo.aluno_id.in_(aluno_ids)).delete(synchronize_session=False)
                elif hasattr(TurmaCargo, 'user_id'):
                    db.session.query(TurmaCargo).filter(TurmaCargo.user_id.in_(student_ids)).delete(synchronize_session=False)

                if hasattr(DisciplinaTurma, 'aluno_id') and aluno_ids:
                    db.session.query(DisciplinaTurma).filter(DisciplinaTurma.aluno_id.in_(aluno_ids)).delete(synchronize_session=False)
                elif hasattr(DisciplinaTurma, 'user_id'):
                    db.session.query(DisciplinaTurma).filter(DisciplinaTurma.user_id.in_(student_ids)).delete(synchronize_session=False)
                # --------------------------------------------------------

                db.session.query(Resposta).filter(Resposta.user_id.in_(student_ids)).delete(synchronize_session=False)
                
                # --- CAÇA-FANTASMAS DE INSTRUTORES RESIDUAIS ---
                # Verifica se há perfis na tabela 'instrutores' ligados a estes alunos (perfis fantasmas)
                instrutores_fantasma = db.session.scalars(select(Instrutor).where(Instrutor.user_id.in_(student_ids))).all()
                if instrutores_fantasma:
                    inst_ids = [i.id for i in instrutores_fantasma]
                    # Limpar as dependências desse instrutor fantasma usando hasattr para evitar AttributeError
                    delegacoes_fantasma = db.session.scalars(select(DelegacaoProva).where(DelegacaoProva.instrutor_id.in_(inst_ids))).all()
                    if delegacoes_fantasma:
                        del_ids = [d.id for d in delegacoes_fantasma]
                        db.session.query(RascunhoProva).filter(RascunhoProva.delegacao_id.in_(del_ids)).delete(synchronize_session=False)
                        db.session.query(DelegacaoProva).filter(DelegacaoProva.instrutor_id.in_(inst_ids)).delete(synchronize_session=False)
                    
                    if hasattr(QuestaoBanco, 'instrutor_id'):
                        db.session.query(QuestaoBanco).filter(QuestaoBanco.instrutor_id.in_(inst_ids)).delete(synchronize_session=False)
                        
                    if hasattr(DisciplinaTurma, 'instrutor_id'):
                        db.session.query(DisciplinaTurma).filter(DisciplinaTurma.instrutor_id.in_(inst_ids)).delete(synchronize_session=False)
                        
                    # Deleta o perfil instrutor fantasma
                    db.session.query(Instrutor).filter(Instrutor.user_id.in_(student_ids)).delete(synchronize_session=False)
                # ------------------------------------------------
                
                # Exclusão total e definitiva das configurações do aluno (referenciam User.id)
                db.session.query(Notification).filter(Notification.user_id.in_(student_ids)).delete(synchronize_session=False)
                db.session.query(PasswordResetToken).filter(PasswordResetToken.user_id.in_(student_ids)).delete(synchronize_session=False)
                db.session.query(PushSubscription).filter(PushSubscription.user_id.in_(student_ids)).delete(synchronize_session=False)
                db.session.query(UserSchool).filter(UserSchool.user_id.in_(student_ids)).delete(synchronize_session=False)
                
                # Deleta a tabela filha `alunos` antes da tabela pai `users`
                db.session.query(Aluno).filter(Aluno.user_id.in_(student_ids)).delete(synchronize_session=False)
                db.session.query(User).filter(User.id.in_(student_ids)).delete(synchronize_session=False)

            # Instrutores (COMPORTAMENTO SEGURO APLICADO E INTERATIVO)
            if 'instrutores' in options and instructor_ids:
                # 1. Obter IDs da tabela instrutores reais
                instrutores_db = db.session.scalars(select(Instrutor).where(Instrutor.user_id.in_(instructor_ids))).all()
                inst_ids_reais = [i.id for i in instrutores_db] if instrutores_db else []

                # 2. Deleta as associações que esse instrutor tem com a Escola atual (Rascunhos antigos, Delegações...)
                if inst_ids_reais:
                    delegacoes = db.session.scalars(select(DelegacaoProva).where(DelegacaoProva.instrutor_id.in_(inst_ids_reais))).all()
                    delegacao_ids = [d.id for d in delegacoes] if delegacoes else []
                    if delegacao_ids:
                        db.session.query(RascunhoProva).filter(RascunhoProva.delegacao_id.in_(delegacao_ids)).delete(synchronize_session=False)
                        
                    db.session.query(DelegacaoProva).filter(DelegacaoProva.instrutor_id.in_(inst_ids_reais)).delete(synchronize_session=False)

                # 3. REGRA DE OURO PARA PROTEGER MÚLTIPLAS ESCOLAS:
                # O instrutor NUNCA é apagado da tabela `users` nem perde suas configurações globais (Banco de Questões).
                # Apenas removemos o vínculo dele com a SUA ESCOLA.
                db.session.query(UserSchool).filter(UserSchool.user_id.in_(instructor_ids), UserSchool.school_id == school_id).delete(synchronize_session=False)

            db.session.commit()
            return True, "Os registros selecionados foram analisados e excluídos com sucesso do banco de dados."

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro crítico no reset customizado da escola: {e}")
            return False, f"Ocorreu um erro ao processar a limpeza: {str(e)}"