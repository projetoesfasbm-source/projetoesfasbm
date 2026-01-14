import logging
from sqlalchemy import select, func, desc, and_
from sqlalchemy.orm import joinedload
from datetime import datetime, date
import traceback # Mantido apenas se necessário para formatação específica, mas preferível logger.exception

from ..models.database import db
from ..models.aluno import Aluno
from ..models.user import User
from ..models.turma import Turma
from ..models.processo_disciplina import ProcessoDisciplina, StatusProcesso
from ..models.fada_avaliacao import FadaAvaliacao
from ..models.discipline_rule import DisciplineRule
from ..models.elogio import Elogio

# Configuração de Log Profissional
logger = logging.getLogger(__name__)

class JusticaService:
    
    FADA_NOTA_INICIAL = 8.0
    FADA_PONTO_ELOGIO = 0.5
    FADA_MAX_NOTA = 10.0

    @staticmethod
    def _ensure_datetime(dt_input):
        """Converte input seguro para DateTime com Timezone."""
        if not dt_input:
            return datetime.now().astimezone()
        if isinstance(dt_input, datetime):
            return dt_input
        if isinstance(dt_input, date):
            return datetime.combine(dt_input, datetime.min.time()).astimezone()
        if isinstance(dt_input, str):
            try:
                return datetime.strptime(dt_input, '%Y-%m-%d').astimezone()
            except ValueError:
                logger.warning(f"Data inválida recebida: {dt_input}. Usando data atual.")
                return datetime.now().astimezone()
        return datetime.now().astimezone()

    @staticmethod
    def get_pontuacao_config(school):
        if not school: return False, 0.0
        if school.npccal_type == 'ctsp': return False, 0.0
        if school.npccal_type in ['cbfpm', 'cspm']: return True, JusticaService.FADA_PONTO_ELOGIO
        return False, 0.0

    @staticmethod
    def get_processos_para_usuario(user, school_id_override=None):
        try:
            query = select(ProcessoDisciplina).join(ProcessoDisciplina.aluno).join(Aluno.turma)

            # 1. Visão do Aluno: Vê os seus, mas filtrado pela escola atual para evitar mistura de dados
            if getattr(user, 'role', '') == 'aluno':
                if not getattr(user, 'aluno_profile', None): 
                    return []
                
                query = query.where(ProcessoDisciplina.aluno_id == user.aluno_profile.id)
                
                # Reforço de segurança: se a escola foi passada, filtra explicitamente
                if school_id_override:
                    query = query.where(Turma.school_id == school_id_override)

            # 2. Visão Admin/Instrutor: Vê todos da escola
            else:
                if not school_id_override: 
                    logger.warning(f"Tentativa de listar processos sem school_id por usuário {user.id}")
                    return [] 
                query = query.where(Turma.school_id == school_id_override)

            query = query.options(
                joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user),
                joinedload(ProcessoDisciplina.regra)
            ).order_by(ProcessoDisciplina.data_ocorrencia.desc())
            
            return db.session.scalars(query).all()

        except Exception as e:
            logger.exception(f"Erro crítico ao listar processos para usuário {user.id}")
            return []

    @staticmethod
    def get_analise_disciplinar_data(school_id):
        if not school_id: return {}
        try:
            base_join = (Aluno, ProcessoDisciplina.aluno_id == Aluno.id)
            turma_join = (Turma, Aluno.turma_id == Turma.id)
            school_filter = (Turma.school_id == school_id)

            # Estatísticas por Status
            stats = db.session.query(ProcessoDisciplina.status, func.count(ProcessoDisciplina.id))\
                .join(*base_join).join(*turma_join).where(school_filter)\
                .group_by(ProcessoDisciplina.status).all()
            
            # Infrações mais comuns
            fatos = db.session.query(ProcessoDisciplina.codigo_infracao, func.count(ProcessoDisciplina.id).label('qtd'))\
                .join(*base_join).join(*turma_join).where(school_filter)\
                .group_by(ProcessoDisciplina.codigo_infracao).order_by(desc('qtd')).limit(5).all()
            
            fatos_fmt = []
            for cod, qtd in fatos:
                txt = "Outros / Sem Código"
                if cod:
                    r = db.session.scalar(select(DisciplineRule).where(DisciplineRule.codigo == str(cod)))
                    if r: txt = r.descricao[:40] + "..."
                fatos_fmt.append({'codigo': cod or 'S/C', 'total': qtd, 'descricao': txt})

            # Alunos com mais ocorrências
            alunos = db.session.query(User.nome_completo, func.count(ProcessoDisciplina.id).label('qtd'))\
                .join(Aluno, ProcessoDisciplina.aluno_id == Aluno.id)\
                .join(User, Aluno.user_id == User.id)\
                .join(Turma, Aluno.turma_id == Turma.id)\
                .where(Turma.school_id == school_id)\
                .group_by(User.nome_completo).order_by(desc('qtd')).limit(5).all()

            stats_dict = {k.value if hasattr(k, 'value') else str(k): v for k, v in stats}

            return {'status_counts': stats_dict, 'common_facts': fatos_fmt, 'top_alunos': [{'nome': a[0], 'total': a[1]} for a in alunos]}
        except Exception as e:
            logger.exception(f"Erro ao gerar análise disciplinar para escola {school_id}")
            return {'status_counts': {}, 'common_facts': [], 'top_alunos': []}

    @staticmethod
    def criar_processo(descricao, observacao, aluno_id, autor_id, pontos=0.0, codigo_infracao=None, regra_id=None, data_ocorrencia=None):
        try:
            dt_final = JusticaService._ensure_datetime(data_ocorrencia)
            final_regra_id = regra_id
            final_codigo = codigo_infracao
            
            if final_regra_id:
                regra = db.session.get(DisciplineRule, final_regra_id)
                if regra:
                    final_codigo = regra.codigo 
            
            novo = ProcessoDisciplina(
                aluno_id=aluno_id, 
                relator_id=autor_id, 
                fato_constatado=descricao, 
                observacao=observacao, 
                pontos=pontos,
                codigo_infracao=final_codigo,
                regra_id=final_regra_id,
                status=StatusProcesso.AGUARDANDO_CIENCIA,
                data_ocorrencia=dt_final
            )
            db.session.add(novo)
            db.session.commit()
            return True, "Registrado com sucesso."
        except Exception as e:
            db.session.rollback()
            logger.exception("Erro ao criar processo disciplinar")
            return False, "Erro interno ao registrar processo."

    @staticmethod
    def finalizar_processo(pid, decisao, fundamentacao, detalhes, turnos_sustacao=None):
        try:
            p = db.session.get(ProcessoDisciplina, pid)
            if not p: return False, "Processo não encontrado."
            
            if turnos_sustacao and decisao == 'Sustação da Dispensa':
                detalhes = f"Sustação: {turnos_sustacao} turnos. {detalhes or ''}"

            p.status = StatusProcesso.FINALIZADO
            p.decisao_final = decisao
            p.fundamentacao = fundamentacao
            p.detalhes_sancao = detalhes
            p.data_decisao = datetime.now().astimezone()
            
            db.session.commit()
            return True, "Processo finalizado com sucesso."
        except Exception as e: 
            db.session.rollback()
            logger.exception(f"Erro ao finalizar processo {pid}")
            return False, "Erro ao finalizar processo."

    @staticmethod
    def deletar_processo(pid):
        try:
            p = db.session.get(ProcessoDisciplina, pid)
            if p:
                db.session.delete(p)
                db.session.commit()
                return True, "Registro excluído."
            return False, "Processo não encontrado."
        except Exception as e: 
            db.session.rollback()
            logger.exception(f"Erro ao deletar processo {pid}")
            return False, "Erro interno ao excluir."

    @staticmethod
    def registrar_ciente(pid, user):
        try:
            p = db.session.get(ProcessoDisciplina, pid)
            if not p or p.aluno.user_id != user.id:
                return False, "Usuário não autorizado."
                
            p.status = StatusProcesso.ALUNO_NOTIFICADO
            p.ciente_aluno = True
            p.data_ciente = datetime.now().astimezone()
            db.session.commit()
            return True, "Ciência registrada."
        except Exception as e: 
            db.session.rollback()
            logger.exception(f"Erro ao registrar ciente no processo {pid}")
            return False, "Erro ao registrar ciência."

    @staticmethod
    def enviar_defesa(pid, texto, user):
        try:
            p = db.session.get(ProcessoDisciplina, pid)
            if not p or p.aluno.user_id != user.id:
                return False, "Não autorizado."
                
            p.status = StatusProcesso.DEFESA_ENVIADA
            p.defesa = texto
            p.data_defesa = datetime.now().astimezone()
            db.session.commit()
            return True, "Defesa enviada com sucesso."
        except Exception as e: 
            db.session.rollback()
            logger.exception(f"Erro ao enviar defesa no processo {pid}")
            return False, "Erro interno ao enviar defesa."

    @staticmethod
    def get_alunos_para_fada(school_id):
        if not school_id: return []
        return db.session.scalars(
            select(Aluno).join(Turma).join(User)
            .where(Turma.school_id == school_id)
            .order_by(User.nome_completo)
        ).all()

    @staticmethod
    def calcular_previa_fada(aluno_id, ciclo_id=None):
        """
        Calcula nota FADA garantindo que apenas registros da escola atual sejam computados.
        """
        notas = {i: JusticaService.FADA_NOTA_INICIAL for i in range(1, 19)}
        try:
            aluno = db.session.get(Aluno, aluno_id)
            if not aluno or not aluno.turma or not aluno.turma.school:
                return notas
            
            escola_id = aluno.turma.school_id

            # Escolas CTSP não possuem pontuação
            if aluno.turma.school.npccal_type == 'ctsp':
                return notas

            # Filtra infrações da escola correta
            punicoes = db.session.scalars(
                select(ProcessoDisciplina)
                .join(Aluno).join(Turma)
                .where(
                    ProcessoDisciplina.aluno_id == aluno_id, 
                    ProcessoDisciplina.status == StatusProcesso.FINALIZADO,
                    Turma.school_id == escola_id 
                )
                .options(joinedload(ProcessoDisciplina.regra))
            ).all()

            for p in punicoes:
                pts = getattr(p, 'pontos', 0.0) or 0.0
                attr = 8 # Padrão: Disciplina
                if p.regra and p.regra.atributo_fada_id:
                    attr = p.regra.atributo_fada_id
                
                if 1 <= attr <= 18:
                    notas[attr] = max(0.0, notas[attr] - float(pts))
            
            # Elogios
            elogios = db.session.scalars(select(Elogio).where(Elogio.aluno_id == aluno_id)).all()
            for e in elogios:
                pts = float(e.pontos) if e.pontos is not None else 0.0
                if e.atributo_1 and 1 <= e.atributo_1 <= 18:
                    notas[e.atributo_1] = min(JusticaService.FADA_MAX_NOTA, notas[e.atributo_1] + pts)
                if e.atributo_2 and 1 <= e.atributo_2 <= 18:
                    notas[e.atributo_2] = min(JusticaService.FADA_MAX_NOTA, notas[e.atributo_2] + pts)
                    
        except Exception as e:
            logger.exception(f"Erro ao calcular FADA para aluno {aluno_id}")
            
        return notas

    @staticmethod
    def salvar_fada(form_data, aluno_id, avaliador_id, nome_avaliador):
        try:
            cid = form_data.get('ciclo_id')
            cid = int(cid) if cid else None
            
            av = db.session.scalar(select(FadaAvaliacao).where(FadaAvaliacao.aluno_id == aluno_id, FadaAvaliacao.ciclo_id == cid))
            if not av:
                av = FadaAvaliacao(aluno_id=aluno_id, ciclo_id=cid)
                db.session.add(av)
            
            av.avaliador_id = avaliador_id
            av.nome_avaliador_custom = nome_avaliador
            av.data_avaliacao = datetime.now().astimezone()
            
            campos = [f'attr_{i}' for i in range(1, 19)]
            colunas_db = [
                'attr_1_expressao', 'attr_2_planejamento', 'attr_3_perseveranca', 
                'attr_4_apresentacao', 'attr_5_lealdade', 'attr_6_tato', 
                'attr_7_equilibrio', 'attr_8_disciplina', 'attr_9_responsabilidade', 
                'attr_10_maturidade', 'attr_11_assiduidade', 'attr_12_pontualidade', 
                'attr_13_diccao', 'attr_14_lideranca', 'attr_15_relacionamento', 
                'attr_16_etica', 'attr_17_produtividade', 'attr_18_eficiencia'
            ]
            
            soma = 0.0
            for field, col in zip(campos, colunas_db):
                try: val = float(form_data.get(field, 8.0))
                except: val = 8.0
                setattr(av, col, val)
                soma += val
            
            av.media_final = soma / 18.0
            av.justificativa_notas = form_data.get('justificativa_notas')
            av.observacoes = form_data.get('observacoes')
            av.adaptacao_carreira = form_data.get('adaptacao_carreira', 'Em adaptação')
            
            db.session.commit()
            return True, "Avaliação salva com sucesso!", av.id
        except Exception as e:
            db.session.rollback()
            logger.exception("Erro ao salvar FADA")
            return False, "Erro ao salvar avaliação.", None

    @staticmethod
    def get_fada_por_id(id): return db.session.get(FadaAvaliacao, id)

    @staticmethod
    def get_processos_por_ids(ids, school_id):
        if not ids or not school_id: return []
        return db.session.scalars(
            select(ProcessoDisciplina)
            .join(Aluno).join(Turma)
            .where(
                ProcessoDisciplina.id.in_(ids),
                Turma.school_id == school_id
            )
        ).all()

    @staticmethod
    def get_finalized_processos(school_id):
        if not school_id: return []
        return db.session.scalars(
            select(ProcessoDisciplina)
            .join(Aluno).join(Turma)
            .where(
                ProcessoDisciplina.status == StatusProcesso.FINALIZADO,
                Turma.school_id == school_id
            )
            .order_by(ProcessoDisciplina.data_decisao.desc())
        ).all()