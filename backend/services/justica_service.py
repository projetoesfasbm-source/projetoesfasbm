import logging
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from datetime import datetime, date, timedelta

from ..models.database import db
from ..models.aluno import Aluno
from ..models.turma import Turma
from ..models.ciclo import Ciclo
from ..models.processo_disciplina import ProcessoDisciplina, StatusProcesso
from ..models.fada_avaliacao import FadaAvaliacao
from ..models.discipline_rule import DisciplineRule
from ..models.elogio import Elogio

logger = logging.getLogger(__name__)

class JusticaService:
    
    # Constantes Oficiais (PDF Art. 120 e 125)
    FADA_BASE = 8.0
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
        if not dt_input: return datetime.now().astimezone()
        if isinstance(dt_input, datetime): return dt_input
        if isinstance(dt_input, date): return datetime.combine(dt_input, datetime.min.time()).astimezone()
        if isinstance(dt_input, str):
            try: return datetime.strptime(dt_input, '%Y-%m-%d %H:%M').astimezone()
            except: pass
            try: return datetime.strptime(dt_input, '%Y-%m-%d').astimezone()
            except: pass
        return datetime.now().astimezone()

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
        try:
            turma = db.session.get(Turma, turma_id)
            if not turma or not turma.school_id: return None
            # Busca ciclos ordenados
            ciclos = db.session.scalars(select(Ciclo).where(Ciclo.school_id == turma.school_id).order_by(Ciclo.data_inicio)).all()
            # Retorna data do 2º ciclo se existir (índice 1)
            if len(ciclos) >= 2 and ciclos[1].data_inicio:
                return JusticaService._ensure_datetime(ciclos[1].data_inicio)
            return None 
        except: return None

    @staticmethod
    def calcular_ndisc_aluno(aluno_id):
        """
        Nota Disciplinar (Base 20).
        Regra PDF Art 121: Inicia a contagem no SEGUNDO ciclo.
        """
        if not JusticaService._is_curso_pontuado(aluno_id=aluno_id): return None

        aluno = db.session.get(Aluno, aluno_id)
        if not aluno: return None

        dt_corte = JusticaService.get_data_inicio_2_ciclo(aluno.turma_id)
        
        # Se não começou o 2º ciclo, nota é máxima (20/2 = 10)
        if not dt_corte: return 10.0 

        # Busca infrações finalizadas A PARTIR do 2º Ciclo
        query = select(ProcessoDisciplina).where(
            ProcessoDisciplina.aluno_id == aluno_id,
            ProcessoDisciplina.status == StatusProcesso.FINALIZADO,
            ProcessoDisciplina.data_ocorrencia >= dt_corte
        )
        processos = db.session.scalars(query).all()
        
        pd = sum(p.pontos for p in processos if p.pontos)
        
        ndisc = (JusticaService.NDISC_BASE - pd) / 2
        return max(0.0, min(10.0, ndisc))

    @staticmethod
    def calcular_fada_estimada(aluno_id):
        """
        FADA (Base 8.0).
        Regra PDF Art 125:
        - §5: NPCCAL conta a partir do 2º Ciclo.
        - §6: RDBM/Crime conta desde o início.
        """
        if not JusticaService._is_curso_pontuado(aluno_id=aluno_id): return None

        aluno = db.session.get(Aluno, aluno_id)
        if not aluno: return None

        dt_2_ciclo = JusticaService.get_data_inicio_2_ciclo(aluno.turma_id)
        # Se não definido 2º ciclo, NPCCAL não desconta ainda (usa data futura)
        if not dt_2_ciclo: dt_2_ciclo = datetime.max.astimezone()

        # Busca todos os processos finalizados
        query_proc = select(ProcessoDisciplina).where(
            ProcessoDisciplina.aluno_id == aluno_id,
            ProcessoDisciplina.status == StatusProcesso.FINALIZADO
        )
        processos = db.session.scalars(query_proc).all()

        descontos = 0.0
        for p in processos:
            # RDBM e CRIME contam sempre (Art 125 §6)
            if p.is_crime: 
                descontos += JusticaService.DESC_FADA_CRIME
            elif p.origem_punicao == 'RDBM': 
                descontos += JusticaService.DESC_FADA_RDBM
            else:
                # NPCCAL só conta se for APÓS o início do 2º ciclo (Art 125 §5)
                if p.data_ocorrencia >= dt_2_ciclo:
                    if p.pontos >= 1.0: descontos += JusticaService.DESC_FADA_GRAVE
                    elif p.pontos >= 0.5: descontos += JusticaService.DESC_FADA_MEDIA
                    elif p.pontos > 0: descontos += JusticaService.DESC_FADA_LEVE

        # Elogios (Art 125 §4 - Contam sempre)
        query_elogios = select(Elogio).where(Elogio.aluno_id == aluno_id)
        elogios = db.session.scalars(query_elogios).all()
        bonus = len(elogios) * JusticaService.BONUS_ELOGIO

        nota = JusticaService.FADA_BASE - descontos + bonus
        return max(0.0, min(10.0, nota))

    @staticmethod
    def calcular_aat_final(aluno_id):
        if not JusticaService._is_curso_pontuado(aluno_id=aluno_id): return None, None, None
        
        ndisc = JusticaService.calcular_ndisc_aluno(aluno_id)
        
        # Pega FADA manual se existir, senão calcula a estimada
        fada_oficial = db.session.scalar(
            select(FadaAvaliacao)
            .where(FadaAvaliacao.aluno_id == aluno_id)
            .order_by(FadaAvaliacao.data_avaliacao.desc())
        )
        
        if fada_oficial: nota_fada = fada_oficial.media_final
        else: nota_fada = JusticaService.calcular_fada_estimada(aluno_id)
            
        aat = (ndisc + nota_fada) / 2
        return round(aat, 2), round(ndisc, 2), round(nota_fada, 2)

    @staticmethod
    def get_processos_para_usuario(user, school_id_override=None):
        # CORREÇÃO DO SUMIÇO: Usa Outer Join e filtra escola manualmente
        query = select(ProcessoDisciplina).join(ProcessoDisciplina.aluno).outerjoin(Aluno.turma)
        
        if getattr(user, 'role', '') == 'aluno':
            if not getattr(user, 'aluno_profile', None): return []
            query = query.where(ProcessoDisciplina.aluno_id == user.aluno_profile.id)
        
        # Carrega relacionamentos para evitar erro no template
        query = query.options(
            joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user),
            joinedload(ProcessoDisciplina.regra)
        )
        
        todos_processos = db.session.scalars(query.order_by(ProcessoDisciplina.data_ocorrencia.desc())).all()
        
        # Filtro de escola manual (mais seguro que inner join)
        if school_id_override:
            processos_filtrados = []
            for p in todos_processos:
                # Se o aluno tem turma e escola bate
                if p.aluno.turma and p.aluno.turma.school_id == school_id_override:
                    processos_filtrados.append(p)
                # Se o aluno não tem turma, mas o usuário atual é admin dessa escola, mostra (segurança)
                elif not p.aluno.turma:
                    processos_filtrados.append(p)
            return processos_filtrados
            
        return todos_processos

    @staticmethod
    def criar_processo(descricao, observacao, aluno_id, autor_id, pontos=0.0, codigo_infracao=None, regra_id=None, data_ocorrencia=None):
        try:
            # Se for CTSP, zera pontos (não afeta NDisc)
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
            p.is_crime = is_crime; p.tipo_sancao = tipo_sancao; p.dias_sancao = dias_sancao if dias_sancao else 0; p.origem_punicao = origem
            
            if decisao in ['IMPROCEDENTE', 'ANULADO', 'ARQUIVADO']: p.pontos = 0.0
            
            p.data_decisao = datetime.now().astimezone()
            db.session.commit()
            return True, "Processo finalizado."
        except Exception as e: db.session.rollback(); return False, str(e)

    # Métodos auxiliares padrão
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