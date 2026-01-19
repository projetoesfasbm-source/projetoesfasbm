# backend/services/justica_service.py
import logging
from datetime import datetime, date, timedelta
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import joinedload

from ..models.database import db
from ..models.aluno import Aluno
from ..models.turma import Turma
from ..models.ciclo import Ciclo
from ..models.school import School
from ..models.processo_disciplina import ProcessoDisciplina, StatusProcesso
from ..models.fada_avaliacao import FadaAvaliacao
from ..models.discipline_rule import DisciplineRule
from ..models.elogio import Elogio

logger = logging.getLogger(__name__)

class JusticaService:
    
    # Constantes Oficiais (PDF Art. 120 e 125)
    FADA_BASE = 8.0        # Base de referência para cálculo estimado
    FADA_MAX_ABSOLUTO = 10.0 # Teto máximo permitido (com mérito) para cálculo manual
    NDISC_BASE = 20.0
    
    # Pesos (PDF Art. 125 §7 e 173)
    DESC_FADA_LEVE = 0.25
    DESC_FADA_MEDIA = 0.50
    DESC_FADA_GRAVE = 1.00
    DESC_FADA_RDBM = 2.00
    DESC_FADA_CRIME = 3.00
    BONUS_ELOGIO = 0.50

    @staticmethod
    def _ensure_datetime(dt_input):
        """
        Converte input para datetime com timezone (aware).
        Resolve o erro de comparação entre naive e aware.
        """
        if dt_input is None:
            return datetime.now().astimezone()
            
        # Se já for datetime
        if isinstance(dt_input, datetime):
            if dt_input.tzinfo is None:
                return dt_input.astimezone() # Torna aware se for naive
            return dt_input
            
        # Se for date (sem hora)
        if isinstance(dt_input, date):
            return datetime.combine(dt_input, datetime.min.time()).astimezone()
            
        # Se for string
        if isinstance(dt_input, str):
            try: return datetime.strptime(dt_input, '%Y-%m-%d %H:%M').astimezone()
            except: pass
            try: return datetime.strptime(dt_input, '%Y-%m-%d').astimezone()
            except: pass
            
        return datetime.now().astimezone()

    @staticmethod
    def _get_safe_far_future():
        """Retorna uma data segura no futuro (Ano 3000) para evitar erro de overflow do datetime.max"""
        return datetime(3000, 1, 1).astimezone()

    @staticmethod
    def _is_curso_pontuado(aluno_id=None, school=None, turma=None):
        """Verifica se é CBFPM ou CSPM (Pontuados). CTSP retorna False."""
        try:
            tipo = None
            if school: 
                tipo = getattr(school, 'npccal_type', '')
            elif turma: 
                tipo = getattr(turma.school, 'npccal_type', '') if turma.school else ''
            elif aluno_id:
                aluno = db.session.get(Aluno, aluno_id)
                if aluno and aluno.turma and aluno.turma.school:
                    tipo = getattr(aluno.turma.school, 'npccal_type', '')
            
            tipo = str(tipo).lower().strip() if tipo else ''
            return tipo in ['cbfpm', 'cspm']
        except:
            return False

    @staticmethod
    def get_data_inicio_2_ciclo(turma_id):
        """Busca a data de início do 2º Ciclo para fins de NPCCAL."""
        try:
            turma = db.session.get(Turma, turma_id)
            if not turma or not turma.school_id: return None
            
            # Busca ciclos ordenados
            ciclos = db.session.scalars(select(Ciclo).where(Ciclo.school_id == turma.school_id).order_by(Ciclo.data_inicio)).all()
            
            # Retorna data do 2º ciclo se existir (índice 1)
            if len(ciclos) >= 2:
                return JusticaService._ensure_datetime(ciclos[1].data_inicio)
            
            # Fallback: Tenta achar pelo nome se a ordem falhar
            ciclo2 = next((c for c in ciclos if '2' in c.nome or 'II' in c.nome), None)
            if ciclo2: return JusticaService._ensure_datetime(ciclo2.data_inicio)
            
            return None 
        except: return None

    @staticmethod
    def get_datas_limites(turma_id):
        """
        Retorna as datas críticas para o cálculo (Art. 125):
        - data_inicio_2_ciclo: Quando começa a contar NPCCAL.
        - data_limite_atitudinal: 40 dias antes da formatura (fim de tudo).
        """
        turma = db.session.get(Turma, turma_id)
        if not turma: return None, None

        dt_inicio_2_ciclo = JusticaService.get_data_inicio_2_ciclo(turma_id)

        # Data Limite (Formatura - 40 dias)
        dt_limite = JusticaService._get_safe_far_future() 
        
        if turma.data_formatura:
            dt_form = JusticaService._ensure_datetime(turma.data_formatura)
            dt_limite = dt_form - timedelta(days=40)
            
        return dt_inicio_2_ciclo, dt_limite

    @staticmethod
    def verificar_elegibilidade_punicao(processo, dt_inicio_2_ciclo, dt_limite_atitudinal):
        """
        Aplica a lógica cirúrgica do Art. 125 para saber se um processo desconta nota.
        Retorna True (Desconta) ou False (Ignora).
        """
        # Garante timezone para comparação segura
        data_fato = JusticaService._ensure_datetime(processo.data_ocorrencia)
        dt_limite = JusticaService._ensure_datetime(dt_limite_atitudinal)
        
        if not data_fato: return False

        # 1. Regra Global: Nada conta nos 40 dias finais (Art 125 Caput)
        if data_fato > dt_limite:
            return False

        # 2. Regra de Crimes e RDBM: Contam desde o início do curso (Art 125 §6)
        if processo.is_crime or processo.origem_punicao == 'RDBM':
            return True

        # 3. Regra NPCCAL: Só conta a partir do 2º Ciclo (Art 125 §5)
        if dt_inicio_2_ciclo:
            # Garante timezone também para o inicio do ciclo
            dt_inicio_safe = JusticaService._ensure_datetime(dt_inicio_2_ciclo)
            if data_fato < dt_inicio_safe:
                return False 
        else:
            # Se não há ciclos cadastrados, NPCCAL não conta
            return False
        
        return True

    @staticmethod
    def calcular_limites_fada(aluno_id, mapa_vinculos=None):
        """
        Calcula o teto máximo permitido para cada um dos 18 atributos.
        
        Args:
            aluno_id: ID do aluno.
            mapa_vinculos: Dict {str(processo_id): atributo_index_1_to_18}.
                           Obrigatório passar se houver punições.
        
        Returns:
            (limites, erro): Tuple onde 'limites' é lista de 18 floats e 'erro' é string ou None.
        """
        # 1. Teto padrão é 10.0 (com mérito)
        limites = [JusticaService.FADA_MAX_ABSOLUTO] * 18
        
        aluno = db.session.get(Aluno, aluno_id)
        if not aluno: return limites, None
        
        dt_inicio, dt_limite = JusticaService.get_datas_limites(aluno.turma_id)
        
        # 2. Busca TODAS as infrações que afetam nota
        stmt = select(ProcessoDisciplina).where(
            ProcessoDisciplina.aluno_id == aluno_id,
            ProcessoDisciplina.status == StatusProcesso.FINALIZADO
        )
        processos = db.session.scalars(stmt).all()
        
        if mapa_vinculos is None: mapa_vinculos = {}
        
        for p in processos:
            if JusticaService.verificar_elegibilidade_punicao(p, dt_inicio, dt_limite):
                # Determina valor do desconto
                desconto = 0.0
                if p.is_crime: desconto = JusticaService.DESC_FADA_CRIME
                elif p.origem_punicao == 'RDBM': desconto = JusticaService.DESC_FADA_RDBM
                elif p.pontos:
                    if p.pontos >= 1.0: desconto = JusticaService.DESC_FADA_GRAVE
                    elif p.pontos >= 0.5: desconto = JusticaService.DESC_FADA_MEDIA
                    else: desconto = JusticaService.DESC_FADA_LEVE
                
                if desconto > 0:
                    # VERIFICAÇÃO OBRIGATÓRIA DE VÍNCULO
                    # O admin DEVE ter dito onde essa punição se encaixa
                    str_pid = str(p.id)
                    if str_pid not in mapa_vinculos or not mapa_vinculos[str_pid]:
                        return limites, f"A infração (ID {p.id}) de {desconto} pontos não foi vinculada a nenhum atributo."
                    
                    try:
                        idx_atributo = int(mapa_vinculos[str_pid]) # 1 a 18
                        if idx_atributo < 1 or idx_atributo > 18: raise ValueError()
                    except:
                        return limites, f"Vínculo inválido para a infração ID {p.id}."

                    # APLICA A TRAVA NO TETO DO ATRIBUTO
                    # Teto = 10.0 - Desconto
                    # Se houver mais de uma punição no mesmo atributo, o teto cai cumulativamente
                    limites[idx_atributo-1] -= desconto

        # Garante que nenhum teto fique negativo (embora improvável)
        limites = [max(0.0, l) for l in limites]
        
        return limites, None

    @staticmethod
    def calcular_ndisc_aluno(aluno_id):
        """
        Nota Disciplinar (Base 20).
        Fórmula: (20 - Pontos Elegíveis) / 2
        """
        if not JusticaService._is_curso_pontuado(aluno_id=aluno_id): return 10.0

        aluno = db.session.get(Aluno, aluno_id)
        if not aluno: return 0.0

        dt_inicio, dt_limite = JusticaService.get_datas_limites(aluno.turma_id)
        
        # Busca infrações finalizadas
        query = select(ProcessoDisciplina).where(
            ProcessoDisciplina.aluno_id == aluno_id,
            ProcessoDisciplina.status == StatusProcesso.FINALIZADO
        )
        processos = db.session.scalars(query).all()
        
        pontos_perdidos = 0.0
        for p in processos:
            if JusticaService.verificar_elegibilidade_punicao(p, dt_inicio, dt_limite):
                # Apenas faltas escolares (NPCCAL) afetam a NDisc
                if p.origem_punicao == 'NPCCAL' and p.pontos:
                    pontos_perdidos += p.pontos
        
        ndisc = (JusticaService.NDISC_BASE - pontos_perdidos) / 2.0
        return max(0.0, min(10.0, ndisc))

    @staticmethod
    def calcular_fada_estimada(aluno_id):
        """
        Cálculo Estimado Ajustado:
        Base Total (144) - Descontos + Bônus / 18.
        """
        if not JusticaService._is_curso_pontuado(aluno_id=aluno_id): return 10.0

        aluno = db.session.get(Aluno, aluno_id)
        if not aluno: return 0.0

        dt_inicio, dt_limite = JusticaService.get_datas_limites(aluno.turma_id)

        # Busca todos os processos finalizados
        query_proc = select(ProcessoDisciplina).where(
            ProcessoDisciplina.aluno_id == aluno_id,
            ProcessoDisciplina.status == StatusProcesso.FINALIZADO
        )
        processos = db.session.scalars(query_proc).all()

        # Elogios
        query_elogios = select(Elogio).where(Elogio.aluno_id == aluno_id)
        elogios = db.session.scalars(query_elogios).all()

        descontos_totais_pontos = 0.0
        for p in processos:
            if not JusticaService.verificar_elegibilidade_punicao(p, dt_inicio, dt_limite):
                continue

            # Hierarquia de Descontos da FADA
            val = 0.0
            if p.is_crime: val = JusticaService.DESC_FADA_CRIME
            elif p.origem_punicao == 'RDBM': val = JusticaService.DESC_FADA_RDBM
            elif p.pontos:
                if p.pontos >= 1.0: val = JusticaService.DESC_FADA_GRAVE
                elif p.pontos >= 0.5: val = JusticaService.DESC_FADA_MEDIA
                else: val = JusticaService.DESC_FADA_LEVE
            descontos_totais_pontos += val

        # Bônus (Contam sempre, limitado a 2 elogios = 1.0 ponto na massa)
        bonus_total = min(len(elogios), 2) * JusticaService.BONUS_ELOGIO

        # Massa Total baseada em 8.0 por atributo
        # (18 atributos * 8.0 Base) - Descontos + Bônus
        total_pontos = (18 * JusticaService.FADA_BASE) - descontos_totais_pontos + bonus_total
        
        media = total_pontos / 18.0
        return max(0.0, min(10.0, media))

    @staticmethod
    def calcular_aat_final(aluno_id):
        if not JusticaService._is_curso_pontuado(aluno_id=aluno_id): return None, None, None
        
        ndisc = JusticaService.calcular_ndisc_aluno(aluno_id)
        
        # Pega FADA manual se existir (Prioridade), senão usa a estimada
        fada_oficial = db.session.scalar(
            select(FadaAvaliacao)
            .where(FadaAvaliacao.aluno_id == aluno_id)
            .order_by(FadaAvaliacao.data_avaliacao.desc())
        )
        
        if fada_oficial: nota_fada = fada_oficial.media_final
        else: nota_fada = JusticaService.calcular_fada_estimada(aluno_id)
            
        aat = (ndisc + nota_fada) / 2.0
        return round(aat, 2), round(ndisc, 2), round(nota_fada, 4)

    @staticmethod
    def get_processos_para_usuario(user, school_id_override=None):
        query = select(ProcessoDisciplina).join(ProcessoDisciplina.aluno).outerjoin(Aluno.turma)
        
        if getattr(user, 'role', '') == 'aluno':
            if not getattr(user, 'aluno_profile', None): return []
            query = query.where(ProcessoDisciplina.aluno_id == user.aluno_profile.id)
        
        query = query.options(
            joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user),
            joinedload(ProcessoDisciplina.regra)
        )
        
        todos_processos = db.session.scalars(query.order_by(ProcessoDisciplina.data_ocorrencia.desc())).all()
        
        if school_id_override:
            processos_filtrados = []
            for p in todos_processos:
                if p.aluno.turma and p.aluno.turma.school_id == school_id_override:
                    processos_filtrados.append(p)
                elif not p.aluno.turma:
                    processos_filtrados.append(p)
            return processos_filtrados
            
        return todos_processos

    @staticmethod
    def criar_processo(descricao, observacao, aluno_id, autor_id, pontos=0.0, codigo_infracao=None, regra_id=None, data_ocorrencia=None):
        try:
            if not JusticaService._is_curso_pontuado(aluno_id=aluno_id): pontos = 0.0
            
            dt = JusticaService._ensure_datetime(data_ocorrencia)
            regra = db.session.get(DisciplineRule, regra_id) if regra_id else None
            cod = regra.codigo if regra else codigo_infracao
            
            novo = ProcessoDisciplina(
                aluno_id=aluno_id, relator_id=autor_id, fato_constatado=descricao, observacao=observacao, 
                pontos=pontos, codigo_infracao=cod, regra_id=regra_id, 
                status=StatusProcesso.AGUARDANDO_CIENCIA, data_ocorrencia=dt, origem_punicao='NPCCAL'
            )
            db.session.add(novo); db.session.commit(); return True, "Sucesso"
        except Exception as e: db.session.rollback(); return False, str(e)
    
    @staticmethod
    def get_pontuacao_config(school):
        if not school: return False, 0.0
        return JusticaService._is_curso_pontuado(school=school), JusticaService.BONUS_ELOGIO

    @staticmethod
    def finalizar_processo(pid, decisao, fundamentacao, detalhes, is_crime=False, tipo_sancao=None, dias_sancao=None, origem='NPCCAL'):
        try:
            p = db.session.get(ProcessoDisciplina, pid)
            if not p: return False, "Processo não encontrado."
            p.status = StatusProcesso.FINALIZADO 
            p.decisao_final = decisao; p.fundamentacao = fundamentacao; p.detalhes_sancao = detalhes
            
            p.is_crime = is_crime
            p.tipo_sancao = tipo_sancao
            p.dias_sancao = dias_sancao if dias_sancao else 0
            p.origem_punicao = origem
            
            if decisao in ['IMPROCEDENTE', 'ANULADO', 'ARQUIVADO']: p.pontos = 0.0
            
            p.data_decisao = datetime.now().astimezone()
            db.session.commit()
            return True, "Processo finalizado."
        except Exception as e: db.session.rollback(); return False, str(e)

    @staticmethod
    def verificar_prazos_revelia_automatica(): return True, [] 
    
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
    def deletar_processo(pid):
        try:
            p = db.session.get(ProcessoDisciplina, pid)
            db.session.delete(p); db.session.commit(); return True, "Ok"
        except: return False, "Erro"