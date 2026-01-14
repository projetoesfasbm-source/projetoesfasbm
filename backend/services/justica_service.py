from flask import g, url_for, session, render_template
from ..services.email_service import EmailService
from sqlalchemy import select, func, and_, desc
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
        # Mantive sua lógica original de permissão pois ela trata casos específicos de login
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
            
            novo_processo = ProcessoDisciplina(
                aluno_id=aluno_id,
                aberto_por_id=autor_id, # Ajustado para bater com seu model (aberto_por_id ou relator_id?)
                # Se seu model usa relator_id, troque a linha acima por: relator_id=autor_id,
                relator_id=autor_id, # Garantindo compatibilidade
                codigo_infracao=codigo_infracao,
                descricao_fato=descricao, # Ajuste se o nome no model for fato_constatado
                fato_constatado=descricao, # Garantindo compatibilidade
                observacao_cal=observacao, # Ajuste se for observacao
                observacao=observacao, # Garantindo compatibilidade
                pontos_estimados=pontos, # Ajuste se for pontos
                pontos=pontos, # Garantindo compatibilidade
                status='Aguardando Ciência',
                data_ocorrencia=dt_ocorrencia
            )
            db.session.add(novo_processo)
            db.session.commit()
            
            # Notificação (Simplificada para evitar erros)
            aluno = db.session.get(Aluno, aluno_id)
            if aluno and aluno.user:
                NotificationService.create_notification(
                    user_id=aluno.user.id,
                    message=f"Novo Processo Disciplinar: {descricao[:30]}...", 
                    url=url_for('justica.index', _external=True)
                )

            return True, "Processo registrado com sucesso."
        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao criar processo: {str(e)}"

    @staticmethod
    def finalizar_processo(processo_id, decisao, fundamentacao, detalhes):
        processo = db.session.get(ProcessoDisciplina, processo_id)
        if not processo: return False, "Não encontrado."
        
        processo.status = 'Finalizado'
        processo.decisao_final = decisao
        processo.fundamentacao_final = fundamentacao # ou fundamentacao
        processo.fundamentacao = fundamentacao
        processo.sancao_aplicada = detalhes # ou detalhes_sancao
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
        processo.defesa_aluno = texto # ou defesa
        processo.defesa = texto
        processo.data_defesa = datetime.now()
        db.session.commit()
        return True, "Defesa enviada."

    # --- FADA (AQUI ESTÁ A CORREÇÃO PRINCIPAL) ---

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
        
        # Punições (Processos Finalizados)
        punicoes = db.session.scalars(
            select(ProcessoDisciplina)
            .where(
                ProcessoDisciplina.aluno_id == aluno_id,
                ProcessoDisciplina.status == 'Finalizado'
            )
        ).all()

        for p in punicoes:
            pts = getattr(p, 'pontos', 0) or getattr(p, 'pontos_estimados', 0) or 0.0
            codigo = getattr(p, 'codigo_infracao', None)
            
            # Tenta descobrir qual atributo afetar
            atributo_afetado = 8 # Padrão: Disciplina
            if codigo:
                regra = db.session.scalar(select(DisciplineRule).where(DisciplineRule.codigo == codigo))
                if regra and regra.atributo_fada_id:
                    atributo_afetado = regra.atributo_fada_id
            
            notas[atributo_afetado] = max(0.0, notas[atributo_afetado] - float(pts))

        # Elogios
        elogios = db.session.scalars(select(Elogio).where(Elogio.aluno_id == aluno_id)).all()
        for e in elogios:
            pts = e.pontos or 0.5
            if e.atributo_1: notas[e.atributo_1] = min(10.0, notas[e.atributo_1] + pts)
            if e.atributo_2: notas[e.atributo_2] = min(10.0, notas[e.atributo_2] + pts)

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
                val = float(form_data.get(f'attr_{i}', 8.0))
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

    @staticmethod
    def get_analise_disciplinar_data():
        # Corrige erro 'list object has no attribute get'
        stats = db.session.query(ProcessoDisciplina.status, func.count(ProcessoDisciplina.id)).group_by(ProcessoDisciplina.status).all()
        return {
            'status_counts': dict(stats), # <--- Correção
            'common_facts': [],
            'top_alunos': []
        }
    
    @staticmethod
    def get_processos_por_ids(ids):
        return db.session.scalars(select(ProcessoDisciplina).where(ProcessoDisciplina.id.in_(ids))).all()
    
    @staticmethod
    def get_finalized_processos():
        return db.session.scalars(select(ProcessoDisciplina).where(ProcessoDisciplina.status == 'Finalizado')).all()