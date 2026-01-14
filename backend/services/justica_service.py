from flask import g, url_for, session
from ..services.email_service import EmailService
from sqlalchemy import select, func, desc, and_
from datetime import datetime, timezone
from ..models.database import db
from ..models.aluno import Aluno
from ..models.user import User
from ..models.turma import Turma
from ..models.user_school import UserSchool
from ..models.processo_disciplina import ProcessoDisciplina
from ..models.fada_avaliacao import FadaAvaliacao
from ..models.discipline_rule import DisciplineRule
from ..models.elogio import Elogio
from ..models.ciclo import Ciclo
from ..services.notification_service import NotificationService
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError

class JusticaService:
    
    @staticmethod
    def get_processos_para_usuario(user):
        """Busca processos relevantes com base no perfil do usuário."""
        # Lógica robusta de permissão (mantendo sua estrutura original que funciona para login)
        if getattr(user, 'is_cal', False) or getattr(user, 'is_admin_escola', False) or getattr(user, 'is_programador', False) or getattr(user, 'role', '') == 'super_admin':
            
            school_id_to_load = None
            if user.role in ['super_admin', 'programador']:
                school_id_to_load = session.get('view_as_school_id')
            
            if not school_id_to_load:
                if hasattr(user, 'temp_active_school_id'):
                    school_id_to_load = user.temp_active_school_id
                elif session.get('active_school_id'):
                    school_id_to_load = int(session.get('active_school_id'))

            if not school_id_to_load:
                return [] 
            
            query = (
                select(ProcessoDisciplina)
                .join(Aluno, ProcessoDisciplina.aluno_id == Aluno.id)
                .join(User, Aluno.user_id == User.id)
                .join(UserSchool, User.id == UserSchool.user_id) 
                .where(UserSchool.school_id == school_id_to_load) 
                .options(
                    joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user),
                    joinedload(ProcessoDisciplina.relator)
                )
                .distinct()
                .order_by(ProcessoDisciplina.data_ocorrencia.desc())
            )
            return db.session.scalars(query).all()
        else:
            # Visão do Aluno Comum
            if not getattr(user, 'aluno_profile', None):
                return [] 
            
            query = (
                select(ProcessoDisciplina)
                .where(ProcessoDisciplina.aluno_id == user.aluno_profile.id)
                .options(joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user))
                .order_by(ProcessoDisciplina.data_ocorrencia.desc())
            )
            return db.session.scalars(query).all()

    @staticmethod
    def criar_processo(descricao, observacao, aluno_id, autor_id, pontos=0.0, codigo_infracao=None, data_ocorrencia=None):
        try:
            dt_ocorrencia = data_ocorrencia if data_ocorrencia else datetime.now().date()
            
            # Mapeamento de campos para garantir compatibilidade com o Model
            novo_processo = ProcessoDisciplina(
                aluno_id=aluno_id,
                relator_id=autor_id, # Usando relator_id conforme padrão
                codigo_infracao=codigo_infracao,
                fato_constatado=descricao, # Mapeia 'descricao' do controller para 'fato_constatado'
                observacao=observacao,
                pontos=pontos,
                status='Aguardando Ciência',
                data_ocorrencia=dt_ocorrencia
            )
            db.session.add(novo_processo)
            db.session.commit()
            
            # Notificação (dentro de try/except silencioso para não quebrar o fluxo principal)
            try:
                aluno = db.session.get(Aluno, aluno_id)
                if aluno and aluno.user:
                    NotificationService.create_notification(
                        user_id=aluno.user.id,
                        message=f"Novo Processo Disciplinar: {str(descricao)[:30]}...", 
                        url=url_for('justica.index', _external=True)
                    )
            except:
                pass # Ignora erro de notificação para garantir o registro

            return True, "Processo registrado com sucesso."
        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao criar processo: {str(e)}"

    @staticmethod
    def finalizar_processo(processo_id, decisao, fundamentacao, detalhes):
        processo = db.session.get(ProcessoDisciplina, processo_id)
        if not processo: return False, "Processo não encontrado."
        
        processo.status = 'Finalizado'
        processo.decisao_final = decisao
        processo.fundamentacao = fundamentacao
        processo.detalhes_sancao = detalhes
        processo.data_decisao = datetime.now()
        
        db.session.commit()
        return True, "Processo finalizado."

    @staticmethod
    def deletar_processo(processo_id):
        processo = db.session.get(ProcessoDisciplina, processo_id)
        if not processo: return False, "Não encontrado."
        try:
            db.session.delete(processo)
            db.session.commit()
            return True, "Excluído."
        except:
            db.session.rollback()
            return False, "Erro ao excluir."

    @staticmethod
    def registrar_ciente(processo_id, user):
        processo = db.session.get(ProcessoDisciplina, processo_id)
        if not processo: return False, "Erro."
        processo.status = 'Aluno Notificado'
        processo.ciente_aluno = True
        processo.data_ciente = datetime.now()
        db.session.commit()
        return True, "Ciente registrado."

    @staticmethod
    def enviar_defesa(processo_id, texto, user):
        processo = db.session.get(ProcessoDisciplina, processo_id)
        if not processo: return False, "Erro."
        processo.status = 'Defesa Enviada'
        processo.defesa = texto
        processo.data_defesa = datetime.now()
        db.session.commit()
        return True, "Defesa enviada."

    # --- FADA ---

    @staticmethod
    def get_alunos_para_fada(school_id):
        return db.session.scalars(
            select(Aluno)
            .join(User)
            .join(UserSchool)
            .where(UserSchool.school_id == school_id, User.role == 'aluno')
            .order_by(User.nome_completo)
        ).all()

    @staticmethod
    def calcular_previa_fada(aluno_id, ciclo_id=None):
        """Calcula a nota FADA automática (8.0 base - punições + elogios)."""
        notas = {i: 8.0 for i in range(1, 19)}
        
        try:
            # Punições (Processos Finalizados)
            punicoes = db.session.scalars(
                select(ProcessoDisciplina)
                .where(
                    ProcessoDisciplina.aluno_id == aluno_id,
                    ProcessoDisciplina.status == 'Finalizado'
                )
            ).all()

            for p in punicoes:
                pts = getattr(p, 'pontos', 0) or 0.0
                codigo = getattr(p, 'codigo_infracao', None)
                
                # Tenta descobrir qual atributo afetar
                atributo_afetado = 8 # Padrão: Disciplina
                if codigo:
                    regra = db.session.scalar(select(DisciplineRule).where(DisciplineRule.codigo == str(codigo)))
                    if regra and regra.atributo_fada_id:
                        atributo_afetado = regra.atributo_fada_id
                
                if 1 <= atributo_afetado <= 18:
                    notas[atributo_afetado] = max(0.0, notas[atributo_afetado] - float(pts))

            # Elogios
            elogios = db.session.scalars(select(Elogio).where(Elogio.aluno_id == aluno_id)).all()
            for e in elogios:
                pts = e.pontos or 0.5
                if e.atributo_1 and 1 <= e.atributo_1 <= 18: 
                    notas[e.atributo_1] = min(10.0, notas[e.atributo_1] + pts)
                if e.atributo_2 and 1 <= e.atributo_2 <= 18: 
                    notas[e.atributo_2] = min(10.0, notas[e.atributo_2] + pts)
        except Exception:
            pass # Em caso de erro no cálculo, retorna notas padrão 8.0

        return notas

    @staticmethod
    def salvar_fada(form_data, aluno_id, avaliador_id, nome_avaliador, dados_calculados=None):
        try:
            ciclo_id = form_data.get('ciclo_id')
            avaliacao = db.session.scalar(
                select(FadaAvaliacao).where(FadaAvaliacao.aluno_id == aluno_id, FadaAvaliacao.ciclo_id == ciclo_id)
            )
            
            if not avaliacao:
                avaliacao = FadaAvaliacao(aluno_id=aluno_id, ciclo_id=ciclo_id)
                db.session.add(avaliacao)

            avaliacao.avaliador_id = avaliador_id
            avaliacao.nome_avaliador_custom = nome_avaliador
            avaliacao.data_avaliacao = datetime.now()
            
            # Salva atributos (tenta pegar do form, se não, usa 8.0)
            mapa_atributos = [
                'attr_1_expressao', 'attr_2_planejamento', 'attr_3_perseveranca', 'attr_4_apresentacao',
                'attr_5_lealdade', 'attr_6_tato', 'attr_7_equilibrio', 'attr_8_disciplina',
                'attr_9_responsabilidade', 'attr_10_maturidade', 'attr_11_assiduidade', 'attr_12_pontualidade',
                'attr_13_diccao', 'attr_14_lideranca', 'attr_15_relacionamento', 'attr_16_etica',
                'attr_17_produtividade', 'attr_18_eficiencia'
            ]
            
            total = 0
            for i, campo in enumerate(mapa_atributos, 1):
                try:
                    val = float(form_data.get(f'attr_{i}', 8.0))
                except:
                    val = 8.0
                setattr(avaliacao, campo, val)
                total += val
            
            avaliacao.media_final = total / 18.0
            
            # Campos extras de texto
            avaliacao.justificativa_notas = form_data.get('justificativa_notas')
            avaliacao.observacoes = form_data.get('observacoes')
            avaliacao.adaptacao_carreira = form_data.get('adaptacao_carreira')

            db.session.commit()
            return True, "Avaliação salva com sucesso!", avaliacao.id
        except Exception as e:
            db.session.rollback()
            return False, f"Erro: {e}", None

    @staticmethod
    def get_fada_por_id(id):
        return db.session.get(FadaAvaliacao, id)

    # --- ANÁLISE FILTRADA POR ESCOLA ---
    @staticmethod
    def get_analise_disciplinar_data():
        try:
            active_school = g.get('active_school')
            # Retorno vazio seguro se não houver escola
            if not active_school: 
                return {'status_counts': {}, 'common_facts': [], 'top_alunos': []}

            # Subquery para filtrar alunos DA ESCOLA ATIVA
            subquery = select(Aluno.id)\
                .join(User, Aluno.user_id == User.id)\
                .join(UserSchool, User.id == UserSchool.user_id)\
                .where(UserSchool.school_id == active_school.id, User.role == 'aluno')

            # 1. Estatísticas por Status
            stats = db.session.query(ProcessoDisciplina.status, func.count(ProcessoDisciplina.id))\
                .filter(ProcessoDisciplina.aluno_id.in_(subquery))\
                .group_by(ProcessoDisciplina.status).all()
            
            status_counts = dict(stats)

            # 2. Fatos Comuns
            fatos = db.session.query(ProcessoDisciplina.codigo_infracao, func.count(ProcessoDisciplina.id).label('qtd'))\
                .filter(ProcessoDisciplina.aluno_id.in_(subquery))\
                .group_by(ProcessoDisciplina.codigo_infracao)\
                .order_by(desc('qtd')).limit(5).all()
            
            fatos_formatados = []
            for cod, qtd in fatos:
                desc_texto = "..."
                if cod:
                    try:
                        r = db.session.query(DisciplineRule).filter_by(codigo=str(cod)).first()
                        if r: desc_texto = r.descricao[:30] + "..."
                    except:
                        pass
                fatos_formatados.append({'codigo': cod or 'S/C', 'total': qtd, 'descricao': desc_texto})

            # 3. Alunos com mais registros
            alunos = db.session.query(User.nome_completo, func.count(ProcessoDisciplina.id).label('qtd'))\
                .join(Aluno, ProcessoDisciplina.aluno_id == Aluno.id)\
                .join(User, Aluno.user_id == User.id)\
                .filter(ProcessoDisciplina.aluno_id.in_(subquery))\
                .group_by(User.nome_completo)\
                .order_by(desc('qtd')).limit(5).all()

            return {
                'status_counts': status_counts, 
                'common_facts': fatos_formatados,
                'top_alunos': [{'nome': a[0], 'total': a[1]} for a in alunos]
            }
        except Exception as e:
            # Em caso de erro crítico no DB, retorna vazio para não derrubar o site
            print(f"Erro na análise: {e}")
            return {'status_counts': {}, 'common_facts': [], 'top_alunos': []}
    
    @staticmethod
    def get_processos_por_ids(ids):
        return db.session.scalars(select(ProcessoDisciplina).where(ProcessoDisciplina.id.in_(ids))).all()
    
    @staticmethod
    def get_finalized_processos():
        return db.session.scalars(select(ProcessoDisciplina).where(ProcessoDisciplina.status == 'Finalizado')).all()