import logging
from sqlalchemy import select, func, desc, and_
from sqlalchemy.orm import joinedload
from datetime import datetime, date, timedelta
import traceback

from ..models.database import db
from ..models.aluno import Aluno
from ..models.user import User
from ..models.turma import Turma
from ..models.ciclo import Ciclo
from ..models.processo_disciplina import ProcessoDisciplina, StatusProcesso
from ..models.fada_avaliacao import FadaAvaliacao
from ..models.discipline_rule import DisciplineRule
from ..models.elogio import Elogio

logger = logging.getLogger(__name__)

class JusticaService:
    
    FADA_NOTA_INICIAL = 8.0
    FADA_PONTO_ELOGIO = 0.5
    FADA_MAX_NOTA = 10.0
    CODIGO_REVELIA = "REVELIA-AUTO"

    @staticmethod
    def _ensure_datetime(dt_input):
        """Converte entradas variadas para datetime timezone-aware."""
        if not dt_input: 
            return datetime.now().astimezone()
        if isinstance(dt_input, datetime): 
            return dt_input
        if isinstance(dt_input, date): 
            return datetime.combine(dt_input, datetime.min.time()).astimezone()
        if isinstance(dt_input, str):
            dt_input = dt_input.strip()
            try:
                return datetime.strptime(dt_input, '%Y-%m-%d %H:%M').astimezone()
            except ValueError:
                pass
            try: 
                return datetime.strptime(dt_input, '%Y-%m-%d').astimezone()
            except ValueError:
                pass
            try:
                return datetime.strptime(dt_input, '%d/%m/%Y').astimezone()
            except ValueError:
                return datetime.now().astimezone()
        return datetime.now().astimezone()
    
    @staticmethod
    def get_pontuacao_config(school):
        if not school: return False, 0.0
        if school.npccal_type == 'ctsp': return False, 0.0
        if school.npccal_type in ['cbfpm', 'cspm']: return True, JusticaService.FADA_PONTO_ELOGIO
        return False, 0.0

    @staticmethod
    def verificar_prazos_revelia_automatica():
        try:
            limite = datetime.now().astimezone() - timedelta(hours=24)
            # Comparação direta com string (sem .value)
            processos = db.session.scalars(select(ProcessoDisciplina).where(ProcessoDisciplina.status == StatusProcesso.AGUARDANDO_CIENCIA).where(ProcessoDisciplina.data_ocorrencia <= limite)).all()
            log_msgs = []
            for p in processos:
                p.status = StatusProcesso.ALUNO_NOTIFICADO
                p.ciente_aluno = True
                p.data_ciente = datetime.now().astimezone()
                p.observacao = (p.observacao or "") + "\n[SISTEMA] Ciência dada por REVELIA (24h expiradas)."
                
                nova_infracao = ProcessoDisciplina(
                    aluno_id=p.aluno_id, relator_id=p.relator_id,
                    fato_constatado=f"Deixou de dar ciência no processo disciplinar ID {p.id} no prazo de 24h.",
                    codigo_infracao=JusticaService.CODIGO_REVELIA, pontos=0.5, origem_punicao='NPCCAL',
                    status=StatusProcesso.AGUARDANDO_CIENCIA, data_ocorrencia=datetime.now().astimezone()
                )
                db.session.add(nova_infracao)
                log_msgs.append(f"Proc {p.id} -> Revelia + Nova Infração.")
            db.session.commit()
            return True, log_msgs
        except Exception as e:
            db.session.rollback()
            logger.exception("Erro CRON Revelia")
            return False, str(e)

    @staticmethod
    def calcular_ndisc_aluno(aluno_id):
        aluno = db.session.get(Aluno, aluno_id)
        if not aluno: return 0.0
        turma = aluno.turma
        if not turma: return 10.0
        
        tipo_escola = 'cbfpm'
        if turma.school and turma.school.npccal_type: tipo_escola = turma.school.npccal_type
        idx_corte = 0
        if tipo_escola in ['cbfpm', 'ctsp']: idx_corte = 1
        elif tipo_escola == 'cspm': idx_corte = 2
        
        data_corte = None
        ciclos = db.session.scalars(select(Ciclo).where(Ciclo.school_id == turma.school_id).order_by(Ciclo.data_inicio)).all()
        if ciclos and idx_corte < len(ciclos):
            if ciclos[idx_corte].data_inicio: data_corte = ciclos[idx_corte].data_inicio

        # Comparação direta com string (sem .value)
        query = select(ProcessoDisciplina).where(ProcessoDisciplina.aluno_id == aluno_id, ProcessoDisciplina.status == StatusProcesso.FINALIZADO, ProcessoDisciplina.pontos > 0)
        if data_corte:
            dt_corte = datetime.combine(data_corte, datetime.min.time()).astimezone()
            query = query.where(ProcessoDisciplina.data_ocorrencia >= dt_corte)
            
        processos = db.session.scalars(query).all()
        nota = (20.0 - sum(p.pontos for p in processos)) / 2
        return max(0.0, min(10.0, nota))

    @staticmethod
    def finalizar_processo(pid, decisao, fundamentacao, detalhes, is_crime=False, tipo_sancao=None, dias_sancao=None, origem='NPCCAL'):
        try:
            p = db.session.get(ProcessoDisciplina, pid)
            if not p: return False, "Processo não encontrado."
            
            # Atribuição direta da string
            p.status = StatusProcesso.FINALIZADO 
            p.decisao_final = decisao
            p.fundamentacao = fundamentacao
            p.detalhes_sancao = detalhes
            p.is_crime = is_crime
            p.tipo_sancao = tipo_sancao
            p.dias_sancao = dias_sancao if dias_sancao else 0
            p.origem_punicao = origem
            
            if decisao in ['IMPROCEDENTE', 'ANULADO', 'ARQUIVADO']: 
                p.pontos = 0.0
            
            p.data_decisao = datetime.now().astimezone()
            db.session.commit()
            return True, "Processo finalizado."
        except Exception as e: 
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def get_processos_para_usuario(user, school_id_override=None):
        try:
            query = select(ProcessoDisciplina).join(ProcessoDisciplina.aluno).outerjoin(Aluno.turma)
            if getattr(user, 'role', '') == 'aluno':
                if not getattr(user, 'aluno_profile', None): return []
                query = query.where(ProcessoDisciplina.aluno_id == user.aluno_profile.id)
                if school_id_override: query = query.where(Turma.school_id == school_id_override)
            else:
                if school_id_override: query = query.where(Turma.school_id == school_id_override)
            query = query.options(joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user), joinedload(ProcessoDisciplina.regra))
            return db.session.scalars(query.order_by(ProcessoDisciplina.data_ocorrencia.desc())).all()
        except: return []

    @staticmethod
    def criar_processo(descricao, observacao, aluno_id, autor_id, pontos=0.0, codigo_infracao=None, regra_id=None, data_ocorrencia=None):
        try:
            dt = JusticaService._ensure_datetime(data_ocorrencia)
            regra = db.session.get(DisciplineRule, regra_id) if regra_id else None
            cod = regra.codigo if regra else codigo_infracao
            novo = ProcessoDisciplina(
                aluno_id=aluno_id, relator_id=autor_id, fato_constatado=descricao, observacao=observacao, pontos=pontos, 
                codigo_infracao=cod, regra_id=regra_id, 
                status=StatusProcesso.AGUARDANDO_CIENCIA, # String direta
                data_ocorrencia=dt, origem_punicao='NPCCAL'
            )
            db.session.add(novo); db.session.commit(); return True, "Sucesso"
        except Exception as e: db.session.rollback(); return False, str(e)

    @staticmethod
    def deletar_processo(pid):
        try:
            p = db.session.get(ProcessoDisciplina, pid)
            if p: db.session.delete(p); db.session.commit(); return True, "Deletado"
            return False, "404"
        except: db.session.rollback(); return False, "Erro"

    @staticmethod
    def registrar_ciente(pid, user):
        try:
            p = db.session.get(ProcessoDisciplina, pid)
            p.status = StatusProcesso.ALUNO_NOTIFICADO; p.ciente_aluno = True; p.data_ciente = datetime.now().astimezone()
            db.session.commit(); return True, "Ciente"
        except: db.session.rollback(); return False, "Erro"

    @staticmethod
    def enviar_defesa(pid, texto, user):
        try:
            p = db.session.get(ProcessoDisciplina, pid)
            p.status = StatusProcesso.DEFESA_ENVIADA; p.defesa = texto; p.data_defesa = datetime.now().astimezone()
            db.session.commit(); return True, "Enviado"
        except: db.session.rollback(); return False, "Erro"
        
    @staticmethod
    def get_analise_disciplinar_data(school_id): return {}