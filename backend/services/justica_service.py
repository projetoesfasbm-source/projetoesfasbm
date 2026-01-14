# backend/services/justica_service.py

from flask import g, url_for, session, render_template
from ..services.email_service import EmailService
from sqlalchemy import select, func, and_
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
        """
        Busca processos relevantes.
        Verifica user.is_cal (contexto da escola) em vez de apenas role global.
        """
        # Verifica se é CAL, Admin Escola, Programador ou Super Admin
        if getattr(user, 'is_cal', False) or getattr(user, 'is_admin_escola', False) or getattr(user, 'is_programador', False) or getattr(user, 'role', '') == 'super_admin':
            
            school_id_to_load = None
            # 1. Tenta pegar da sessão (Programador/Super Admin)
            if user.role in ['super_admin', 'programador']:
                school_id_to_load = session.get('view_as_school_id')
            
            # 2. Tenta pegar do contexto injetado (CAL/Admin Escola)
            if not school_id_to_load:
                # Tenta pegar do atributo temporário injetado no app.py
                if hasattr(user, 'temp_active_school_id'):
                    school_id_to_load = user.temp_active_school_id
                # Fallback para session direta
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
                .distinct() # Garante que não duplique se houver joins estranhos
                .order_by(ProcessoDisciplina.data_ocorrencia.desc())
            )
        else:
            # Visão do Aluno Comum (vê apenas os seus)
            if not getattr(user, 'aluno_profile', None):
                return [] 
            
            query = (
                select(ProcessoDisciplina)
                .where(ProcessoDisciplina.aluno_id == user.aluno_profile.id)
                .options(
                    joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user),
                    joinedload(ProcessoDisciplina.relator)
                )
                .order_by(ProcessoDisciplina.data_ocorrencia.desc())
            )
            
        return db.session.scalars(query).all()

    @staticmethod
    def criar_processo(fato, observacao, aluno_id, relator_id, pontos: float = 0.0, codigo_infracao=None, data_ocorrencia=None):
        """
        Cria um novo processo disciplinar.
        Atualizado para aceitar codigo_infracao e data_ocorrencia para suporte à Mala Direta.
        """
        aluno = db.session.get(Aluno, aluno_id)
        if not aluno:
            return False, "Aluno não encontrado."
        
        aluno_user = aluno.user
        if not aluno_user or not aluno_user.email:
             # Em alguns casos antigos pode não ter email, mas prossegue o registro
             pass 

        try:
            # Se data_ocorrencia não for passada, usa hoje
            dt_ocorrencia = data_ocorrencia if data_ocorrencia else datetime.now().date()

            novo_processo = ProcessoDisciplina(
                aluno_id=aluno_id,
                relator_id=relator_id,
                fato_constatado=fato,
                observacao=observacao,
                pontos=pontos,
                codigo_infracao=codigo_infracao, # Novo campo
                data_ocorrencia=dt_ocorrencia,   # Novo campo
                status='Aguardando Ciência' 
            )
            db.session.add(novo_processo)
            db.session.flush()

            url_notificacao = url_for('justica.index', _external=True)

            if aluno_user and aluno_user.email:
                EmailService.send_justice_notification_email(
                    user=aluno_user,
                    processo=novo_processo,
                    url=url_notificacao
                )

            if aluno_user:
                NotificationService.create_notification(
                    user_id=aluno_user.id,
                    message=f"Novo Processo Disciplinar: {fato[:50]}...", 
                    url=url_notificacao
                )
            
            db.session.commit()
            return True, "Processo disciplinar registrado e aluno notificado!"
        
        except SQLAlchemyError as e:
            db.session.rollback()
            return False, f"Erro de banco de dados: {e}"
        except Exception as e:
            db.session.rollback()
            return False, f"Erro inesperado: {e}"

    @staticmethod
    def registrar_ciente(processo_id, user):
        processo = db.session.get(ProcessoDisciplina, processo_id)
        if not processo or processo.aluno_id != user.aluno_profile.id:
            return False, "Processo não encontrado ou não pertence a você."
        
        if processo.status != 'Aguardando Ciência':
            return False, "Este processo não está mais aguardando ciência."
            
        try:
            processo.status = 'Aluno Notificado'
            processo.data_ciente = datetime.now(timezone.utc)
            db.session.commit()
            
            if processo.relator_id:
                NotificationService.create_notification(
                    user_id=processo.relator_id,
                    message=f"O aluno {user.nome_completo} deu ciência do Processo nº {processo.id}.",
                    url=url_for('justica.index', _external=True)
                )
            
            return True, "Ciência registrada com sucesso."
        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao registrar ciência: {e}"

    @staticmethod
    def enviar_defesa(processo_id, defesa, user):
        processo = db.session.get(ProcessoDisciplina, processo_id)
        if not processo or processo.aluno_id != user.aluno_profile.id:
            return False, "Processo não encontrado ou não pertence a você."

        if processo.status != 'Aluno Notificado':
            return False, "O prazo para defesa expirou ou a defesa já foi enviada."

        try:
            processo.defesa = defesa
            processo.data_defesa = datetime.now(timezone.utc)
            processo.status = 'Defesa Enviada'
            db.session.commit()
            
            if processo.relator_id:
                NotificationService.create_notification(
                    user_id=processo.relator_id,
                    message=f"O aluno {user.nome_completo} enviou a defesa para o Processo nº {processo.id}.",
                    url=url_for('justica.index', _external=True)
                )
            
            return True, "Defesa enviada com sucesso."
        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao enviar defesa: {e}"
            
    @staticmethod
    def finalizar_processo(processo_id, decisao, fundamentacao, detalhes_sancao):
        processo = db.session.get(ProcessoDisciplina, processo_id)
        if not processo:
            return False, "Processo não encontrado."
            
        # Permitir finalização se estiver Aberto (criado pelo admin direto) ou em fase de recurso
        if processo.status not in ['Defesa Enviada', 'Aluno Notificado', 'Aguardando Ciência', 'Aberto']:
             return False, "Este processo não está em fase de finalização."
        
        aluno_user = getattr(getattr(processo, 'aluno', None), 'user', None)

        try:
            processo.decisao_final = decisao
            processo.fundamentacao = fundamentacao
            processo.detalhes_sancao = detalhes_sancao
            processo.sancao_final = detalhes_sancao # Campo duplicado para compatibilidade
            processo.data_decisao = datetime.now(timezone.utc)
            processo.status = 'Finalizado' # Antigo 'Concluído' unificado para 'Finalizado'
            
            if aluno_user and aluno_user.email:
                EmailService.send_justice_verdict_email(
                    user=aluno_user,
                    processo=processo
                )

            if aluno_user:
                NotificationService.create_notification(
                    user_id=aluno_user.id,
                    message=f"Seu processo nº {processo.id} foi finalizado. Decisão: {decisao}.",
                    url=url_for('justica.index', _external=True)
                )
            
            db.session.commit()
            return True, "Processo finalizado e aluno notificado!"
        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao finalizar processo: {e}"

    @staticmethod
    def deletar_processo(processo_id):
        processo = db.session.get(ProcessoDisciplina, processo_id)
        if not processo:
            return False, "Processo não encontrado."

        # Permite deletar se ainda não tiver decisão final consolidada ou se for admin
        # if processo.status != 'Aguardando Ciência':
        #    return False, "Não é possível excluir um processo após o aluno dar ciência."
            
        try:
            db.session.delete(processo)
            db.session.commit()
            return True, "Processo excluído com sucesso."
        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao excluir processo: {e}"
            
    @staticmethod
    def get_processos_por_ids(ids):
        query = select(ProcessoDisciplina).where(ProcessoDisciplina.id.in_(ids))
        return db.session.scalars(query).all()
        
    @staticmethod
    def get_finalized_processos():
        active_school = g.get('active_school')
        if not active_school:
            return []
        
        alunos_da_escola = (
            select(Aluno.id)
            .join(User, Aluno.user_id == User.id)
            .join(UserSchool, User.id == UserSchool.user_id)
            .where(UserSchool.school_id == active_school.id)
        ).subquery()
        
        query = (
            select(ProcessoDisciplina)
            .join(alunos_da_escola, ProcessoDisciplina.aluno_id == alunos_da_escola.c.id)
            .where(ProcessoDisciplina.status == 'Finalizado')
            .order_by(ProcessoDisciplina.data_decisao.desc())
        )
        return db.session.scalars(query).all()

    @staticmethod
    def get_analise_disciplinar_data():
        active_school = g.get('active_school')
        if not active_school:
            return {}

        alunos_da_escola = (
            select(Aluno.id)
            .join(User, Aluno.user_id == User.id)
            .join(UserSchool, User.id == UserSchool.user_id)
            .where(UserSchool.school_id == active_school.id)
        ).subquery()

        status_counts = db.session.execute(
            select(ProcessoDisciplina.status, func.count(ProcessoDisciplina.id))
            .join(alunos_da_escola, ProcessoDisciplina.aluno_id == alunos_da_escola.c.id)
            .group_by(ProcessoDisciplina.status)
        ).all()
        
        common_facts = db.session.execute(
            select(ProcessoDisciplina.fato_constatado, func.count(ProcessoDisciplina.id).label('total'))
            .join(alunos_da_escola, ProcessoDisciplina.aluno_id == alunos_da_escola.c.id)
            .group_by(ProcessoDisciplina.fato_constatado)
            .order_by(func.count(ProcessoDisciplina.id).desc())
            .limit(10)
        ).all()
        
        top_alunos = db.session.execute(
            select(User.nome_completo, func.count(ProcessoDisciplina.id).label('total'))
            .join(alunos_da_escola, ProcessoDisciplina.aluno_id == alunos_da_escola.c.id)
            .join(Aluno, ProcessoDisciplina.aluno_id == Aluno.id)
            .join(User, Aluno.user_id == User.id)
            .group_by(User.nome_completo)
            .order_by(func.count(ProcessoDisciplina.id).desc())
            .limit(10)
        ).all()

        return {
            'status_counts': [{'status': s[0], 'total': s[1]} for s in status_counts],
            'common_facts': [{'fato': f[0], 'total': f[1]} for f in common_facts],
            'top_alunos': [{'nome': a[0], 'total': a[1]} for a in top_alunos]
        }
        
    @staticmethod
    def get_alunos_para_fada(school_id):
        query = (
            select(Aluno)
            .join(User, Aluno.user_id == User.id)
            .join(UserSchool, User.id == UserSchool.user_id)
            .where(
                UserSchool.school_id == school_id,
                User.role == 'aluno'
            )
            .options(joinedload(Aluno.user))
            .order_by(User.nome_completo)
        )
        return db.session.scalars(query).all()

    @staticmethod
    def get_fada_por_id(avaliacao_id):
        query = (
            select(FadaAvaliacao)
            .where(FadaAvaliacao.id == avaliacao_id)
            .options(
                joinedload(FadaAvaliacao.aluno).joinedload(Aluno.user),
                joinedload(FadaAvaliacao.avaliador)
            )
        )
        return db.session.scalar(query)

    # --- NOVO: CÁLCULO AUTOMÁTICO (SOLICITADO) ---
    @staticmethod
    def calcular_previa_fada(aluno_id, ciclo_id):
        """
        Calcula a FADA e a NDisc automaticamente baseado no PDF (Art 122 e 125).
        Fórmula NDisc: (20 - Pontos) / 2
        Fórmula FADA: Inicia com 8.0 - Infrações + Elogios (0.5)
        """
        aluno = db.session.get(Aluno, aluno_id)
        ciclo = db.session.get(Ciclo, ciclo_id)
        
        if not aluno or not ciclo:
            return None

        # Datas do ciclo (Art. 126)
        data_ini = ciclo.data_inicio
        data_fim = ciclo.data_fim

        # Inicializar Matriz (Art 125 - Inicia com 8.0)
        notas_atributos = {i: 8.0 for i in range(1, 19)}
        total_pontos_perdidos_ndisc = 0.0

        # Buscar Processos Disciplinares no período (Apenas Finalizados contam nota)
        processos = db.session.query(ProcessoDisciplina).filter(
            ProcessoDisciplina.aluno_id == aluno_id,
            ProcessoDisciplina.data_ocorrencia >= data_ini,
            ProcessoDisciplina.data_ocorrencia <= data_fim,
            ProcessoDisciplina.status == 'Finalizado' 
        ).all()

        for proc in processos:
            pts = proc.pontos or 0.0
            total_pontos_perdidos_ndisc += pts

            # Desconto na FADA via atributo vinculado (novo campo atributo_fada_id)
            # Busca a regra pelo código da infração
            rule = db.session.query(DisciplineRule).filter_by(codigo=proc.codigo_infracao).first()
            if rule and rule.atributo_fada_id and 1 <= rule.atributo_fada_id <= 18:
                # Subtrai os pontos do atributo específico
                notas_atributos[rule.atributo_fada_id] -= pts

        # Buscar Elogios no período
        elogios = db.session.query(Elogio).filter(
            Elogio.aluno_id == aluno_id,
            Elogio.data_elogio >= data_ini,
            Elogio.data_elogio <= data_fim
        ).all()

        for elo in elogios:
            pts = elo.pontos or 0.0
            # Aplica bonificação aos atributos selecionados
            if elo.atributo_1 and 1 <= elo.atributo_1 <= 18:
                notas_atributos[elo.atributo_1] += pts
            if elo.atributo_2 and 1 <= elo.atributo_2 <= 18:
                notas_atributos[elo.atributo_2] += pts

        # Normalizar notas (Min 0, Max 10)
        for k, v in notas_atributos.items():
            if v > 10.0: notas_atributos[k] = 10.0
            if v < 0.0: notas_atributos[k] = 0.0

        # Calcular NDisc (Art 122)
        ndisc = (20.0 - total_pontos_perdidos_ndisc) / 2.0
        if ndisc < 0: ndisc = 0.0
        if ndisc > 10: ndisc = 10.0

        return {
            'notas_atributos': notas_atributos,
            'ndisc': ndisc,
            'total_punicoes': len(processos),
            'total_pontos_perdidos': total_pontos_perdidos_ndisc,
            'total_elogios': len(elogios)
        }

    # --- ATUALIZADO PARA ACEITAR DADOS CALCULADOS OU MANUAIS ---
    @staticmethod
    def salvar_fada(form_data, aluno_id, avaliador_id, nome_avaliador_custom, dados_calculados=None):
        try:
            # Verifica se já existe para atualizar
            ciclo_id = form_data.get('ciclo_id')
            avaliacao = FadaAvaliacao.query.filter_by(aluno_id=aluno_id, ciclo_id=ciclo_id).first()
            
            if not avaliacao:
                avaliacao = FadaAvaliacao(
                    aluno_id=aluno_id, 
                    avaliador_id=avaliador_id,
                    nome_avaliador_custom=nome_avaliador_custom,
                    ciclo_id=ciclo_id
                )
                db.session.add(avaliacao)

            # Se vierem dados calculados (automático), usa eles. Senão, pega do formulário.
            if dados_calculados:
                notas = dados_calculados['notas_atributos']
                # Mapeamento reverso manual (1 -> expressao, etc)
                mapa_atributos = [
                    'attr_1_expressao', 'attr_2_planejamento', 'attr_3_perseveranca', 'attr_4_apresentacao',
                    'attr_5_lealdade', 'attr_6_tato', 'attr_7_equilibrio', 'attr_8_disciplina',
                    'attr_9_responsabilidade', 'attr_10_maturidade', 'attr_11_assiduidade', 'attr_12_pontualidade',
                    'attr_13_diccao', 'attr_14_lideranca', 'attr_15_relacionamento', 'attr_16_etica',
                    'attr_17_produtividade', 'attr_18_eficiencia'
                ]
                for i, campo in enumerate(mapa_atributos, 1):
                    setattr(avaliacao, campo, notas.get(i, 8.0))
            else:
                # Método antigo (Manual)
                for i in range(1, 19):
                    field_name_map = {
                        1: 'attr_1_expressao', 2: 'attr_2_planejamento', 3: 'attr_3_perseveranca',
                        4: 'attr_4_apresentacao', 5: 'attr_5_lealdade', 6: 'attr_6_tato',
                        7: 'attr_7_equilibrio', 8: 'attr_8_disciplina', 9: 'attr_9_responsabilidade',
                        10: 'attr_10_maturidade', 11: 'attr_11_assiduidade', 12: 'attr_12_pontualidade',
                        13: 'attr_13_diccao', 14: 'attr_14_lideranca', 15: 'attr_15_relacionamento',
                        16: 'attr_16_etica', 17: 'attr_17_produtividade', 18: 'attr_18_eficiencia'
                    }
                    field_name = field_name_map.get(i)
                    form_field_name = f'attr_{i}'
                    valor = form_data.get(form_field_name)
                    try:
                        valor_float = float(valor)
                        valor_float = max(0.0, min(10.0, valor_float))
                    except (ValueError, TypeError):
                        valor_float = 8.0
                    
                    if field_name:
                        setattr(avaliacao, field_name, valor_float)

            avaliacao.justificativa_notas = form_data.get('justificativa_notas')
            avaliacao.observacoes = form_data.get('observacoes')
            avaliacao.adaptacao_carreira = form_data.get('adaptacao_carreira', 'Em adaptação à carreira militar')

            db.session.commit()
            
            return True, "Avaliação FADA salva com sucesso.", avaliacao.id
        
        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao salvar a avaliação FADA: {e}"

    @staticmethod
    def export_bi_data(school_id):
        return ProcessoDisciplina.query.filter_by(school_id=school_id).order_by(ProcessoDisciplina.data_ocorrencia.desc()).all()