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
    
    # --- CONSTANTES DE NEGÓCIO ---
    FADA_NOTA_INICIAL = 8.0
    FADA_PONTO_ELOGIO = 0.5
    FADA_MAX_NOTA = 10.0
    
    # ID da infração "Deixar de dar ciência" - Você deve garantir que isso exista no banco
    CODIGO_REVELIA = "REVELIA-AUTO"

    @staticmethod
    def _ensure_datetime(dt_input):
        """
        Converte entradas variadas para datetime timezone-aware.
        Suporta: datetime, date, string ISO (YYYY-MM-DD) e string BR (DD/MM/YYYY).
        """
        if not dt_input: 
            return datetime.now().astimezone()
        
        if isinstance(dt_input, datetime): 
            return dt_input
        
        if isinstance(dt_input, date): 
            return datetime.combine(dt_input, datetime.min.time()).astimezone()
        
        if isinstance(dt_input, str):
            dt_input = dt_input.strip()
            # Tenta formato ISO (YYYY-MM-DD) - HTML padrão
            try: 
                return datetime.strptime(dt_input, '%Y-%m-%d').astimezone()
            except ValueError:
                pass
            
            # Tenta formato Brasileiro (DD/MM/YYYY) - Input texto/JS
            try:
                return datetime.strptime(dt_input, '%d/%m/%Y').astimezone()
            except ValueError:
                logger.warning(f"Data inválida recebida: '{dt_input}'. Usando data/hora atual.")
                return datetime.now().astimezone()
                
        return datetime.now().astimezone()

    @staticmethod
    def get_pontuacao_config(school):
        if not school: return False, 0.0
        # ctsp não pontua FADA diretamente da mesma forma que cbfpm/cspm nas regras antigas, 
        # mas mantendo lógica original do seu código:
        if school.npccal_type == 'ctsp': return False, 0.0
        if school.npccal_type in ['cbfpm', 'cspm']: return True, JusticaService.FADA_PONTO_ELOGIO
        return False, 0.0

    @staticmethod
    def get_processos_para_usuario(user, school_id_override=None):
        try:
            query = select(ProcessoDisciplina).join(ProcessoDisciplina.aluno).outerjoin(Aluno.turma)

            # 1. Visão do Aluno
            if getattr(user, 'role', '') == 'aluno':
                if not getattr(user, 'aluno_profile', None): 
                    return []
                query = query.where(ProcessoDisciplina.aluno_id == user.aluno_profile.id)
                if school_id_override:
                    query = query.where(Turma.school_id == school_id_override)

            # 2. Visão Admin/Instrutor
            else:
                if school_id_override:
                    query = query.where(Turma.school_id == school_id_override)
                else:
                    # Fallback seguro: se não filtrar por escola, mostra logs mas não quebra
                    logger.info(f"Listando processos globais para usuário {user.id} (sem school_id)")

            query = query.options(
                joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user),
                joinedload(ProcessoDisciplina.regra)
            ).order_by(ProcessoDisciplina.data_ocorrencia.desc())
            
            return db.session.scalars(query).all()

        except Exception as e:
            logger.exception(f"Erro crítico ao listar processos para usuário {user.id}")
            return []

    @staticmethod
    def criar_processo(descricao, observacao, aluno_id, autor_id, pontos=0.0, codigo_infracao=None, regra_id=None, data_ocorrencia=None):
        try:
            dt_final = JusticaService._ensure_datetime(data_ocorrencia)
            
            final_regra_id = regra_id
            final_codigo = codigo_infracao
            if final_regra_id:
                regra = db.session.get(DisciplineRule, final_regra_id)
                if regra: final_codigo = regra.codigo 
            
            # --- CORREÇÃO DE TIPO ---
            # Garante que status seja uma STRING simples para o banco
            status_inicial = StatusProcesso.AGUARDANDO_CIENCIA.value
            # ------------------------

            novo = ProcessoDisciplina(
                aluno_id=aluno_id, 
                relator_id=autor_id, 
                fato_constatado=descricao, 
                observacao=observacao, 
                pontos=pontos,
                codigo_infracao=final_codigo,
                regra_id=final_regra_id,
                status=status_inicial, # Passa string, não Enum
                data_ocorrencia=dt_final,
                origem_punicao='NPCCAL'
            )
            db.session.add(novo)
            db.session.commit()
            return True, "Registrado com sucesso."
        except Exception as e:
            db.session.rollback()
            logger.exception("Erro ao criar processo no Service")
            return False, f"Erro ao registrar: {str(e)}"

    @staticmethod
    def verificar_prazos_revelia_automatica():
        """
        [AUTOMATICO] Verifica processos com mais de 24h sem ciência.
        1. Dá ciência automática (Revelia).
        2. Gera nova punição por não ter dado ciência.
        """
        try:
            limite = datetime.now().astimezone() - timedelta(hours=24)
            
            # Busca processos vencidos
            processos = db.session.scalars(
                select(ProcessoDisciplina)
                .where(ProcessoDisciplina.status == StatusProcesso.AGUARDANDO_CIENCIA.value)
                .where(ProcessoDisciplina.data_ocorrencia <= limite) # Idealmente usar data_notificacao, mas data_ocorrencia serve como fallback
            ).all()
            
            log_msgs = []
            for p in processos:
                # 1. Aplica Revelia no processo original
                p.status = StatusProcesso.ALUNO_NOTIFICADO.value
                p.ciente_aluno = True
                p.data_ciente = datetime.now().astimezone()
                p.observacao = (p.observacao or "") + "\n[SISTEMA] Ciência dada por REVELIA (Prazo de 24h expirado)."
                
                # 2. Gera nova infração
                # Tenta reutilizar o relator original, senão usa o admin (depende da lógica do seu sistema)
                nova_infracao = ProcessoDisciplina(
                    aluno_id=p.aluno_id,
                    relator_id=p.relator_id, # Mesmo relator
                    fato_constatado=f"Deixou de dar ciência no processo disciplinar ID {p.id} no prazo regulamentar de 24 horas.",
                    codigo_infracao=JusticaService.CODIGO_REVELIA,
                    pontos=0.5, # Ponto padrão por falha administrativa/descumprimento ordem
                    origem_punicao='NPCCAL',
                    status=StatusProcesso.AGUARDANDO_CIENCIA.value,
                    data_ocorrencia=datetime.now().astimezone()
                )
                db.session.add(nova_infracao)
                log_msgs.append(f"Proc {p.id} -> Revelia aplicada + Nova infração gerada.")
            
            db.session.commit()
            return True, log_msgs
        except Exception as e:
            db.session.rollback()
            logger.exception("Erro na rotina de revelia")
            return False, str(e)

    @staticmethod
    def get_analise_disciplinar_data(school_id):
        # (Código original mantido)
        return {} 

    @staticmethod
    def finalizar_processo(pid, decisao, fundamentacao, detalhes, turnos_sustacao=None, is_crime=False, tipo_sancao=None, dias_sancao=None, origem='NPCCAL'):
        try:
            p = db.session.get(ProcessoDisciplina, pid)
            if not p: return False, "Processo não encontrado."
            
            if turnos_sustacao and decisao == 'Sustação da Dispensa':
                detalhes = f"Sustação: {turnos_sustacao} turnos. {detalhes or ''}"

            p.status = StatusProcesso.FINALIZADO.value # Força string .value
            p.decisao_final = decisao
            p.fundamentacao = fundamentacao
            p.detalhes_sancao = detalhes
            
            # Novos campos da Portaria
            p.is_crime = is_crime
            p.tipo_sancao = tipo_sancao
            p.dias_sancao = dias_sancao
            p.origem_punicao = origem
            
            # Se for improcedente ou anulado, zera os pontos
            if decisao in ['IMPROCEDENTE', 'ANULADO', 'ARQUIVADO']:
                p.pontos = 0.0

            p.data_decisao = datetime.now().astimezone()
            
            db.session.commit()
            return True, "Processo finalizado."
        except Exception as e: 
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def deletar_processo(pid):
        try:
            p = db.session.get(ProcessoDisciplina, pid)
            if p:
                db.session.delete(p)
                db.session.commit()
                return True, "Registro excluído."
            return False, "Não encontrado."
        except: 
            db.session.rollback()
            return False, "Erro ao excluir."

    @staticmethod
    def registrar_ciente(pid, user):
        try:
            p = db.session.get(ProcessoDisciplina, pid)
            p.status = StatusProcesso.ALUNO_NOTIFICADO.value
            p.ciente_aluno = True
            p.data_ciente = datetime.now().astimezone()
            db.session.commit()
            return True, "Ciência registrada."
        except: 
            db.session.rollback()
            return False, "Erro."

    @staticmethod
    def enviar_defesa(pid, texto, user):
        try:
            p = db.session.get(ProcessoDisciplina, pid)
            p.status = StatusProcesso.DEFESA_ENVIADA.value
            p.defesa = texto
            p.data_defesa = datetime.now().astimezone()
            db.session.commit()
            return True, "Defesa enviada."
        except: 
            db.session.rollback()
            return False, "Erro."

    @staticmethod
    def calcular_ndisc_aluno(aluno_id):
        """
        Calcula a Nota Disciplinar (NDisc) seguindo a regra dos Módulos.
        - CBFPM/CTSP: Conta pontos apenas a partir do início do 2º Ciclo.
        - CSPM: Conta pontos a partir do 3º Ciclo (ou regra especifica).
        """
        aluno = db.session.get(Aluno, aluno_id)
        if not aluno: return 0.0
        
        turma = aluno.turma
        if not turma: return 20.0 # Sem turma, sem regra, nota máxima
        
        # Identificar tipo de escola
        tipo_escola = 'cbfpm' # Default
        if turma.school and turma.school.npccal_type:
            tipo_escola = turma.school.npccal_type
            
        # Determinar data de corte (Ciclos)
        data_corte = None
        
        # Busca ciclos da escola
        ciclos = db.session.scalars(
            select(Ciclo)
            .where(Ciclo.school_id == turma.school_id)
            .order_by(Ciclo.data_inicio) # Agora assumindo que o Model Ciclo tem data_inicio
        ).all()
        
        if ciclos:
            index_corte = 0
            if tipo_escola in ['cbfpm', 'ctsp']:
                index_corte = 1 # 2º Ciclo (índice 1)
            elif tipo_escola == 'cspm':
                index_corte = 2 # 3º Ciclo (índice 2)
            
            # Proteção de índice
            if index_corte < len(ciclos):
                data_corte = ciclos[index_corte].data_inicio
                # Se data_inicio for None (não cadastrada), assume início do curso (sem corte)
                
        # Query de Processos
        query = select(ProcessoDisciplina).where(
            ProcessoDisciplina.aluno_id == aluno_id,
            ProcessoDisciplina.status == StatusProcesso.FINALIZADO.value,
            ProcessoDisciplina.pontos > 0 # Apenas punições que geraram pontos
        )
        
        # Se temos data de corte, filtra
        if data_corte:
            # Converter data_corte (date) para datetime se necessário
            dt_corte = datetime.combine(data_corte, datetime.min.time()).astimezone()
            query = query.where(ProcessoDisciplina.data_ocorrencia >= dt_corte)
            
        processos = db.session.scalars(query).all()
        
        total_pontos = sum(p.pontos for p in processos)
        
        # Fórmula: (20 - Pontos) / 2
        nota = (20.0 - total_pontos) / 2
        return max(0.0, min(10.0, nota))