from flask import g, url_for, session
from ..services.email_service import EmailService
from sqlalchemy import select, func, desc
from datetime import datetime
from ..models.database import db
from ..models.aluno import Aluno
from ..models.user import User
from ..models.turma import Turma
# from ..models.user_school import UserSchool  <-- REMOVIDO PARA TESTE
from ..models.processo_disciplina import ProcessoDisciplina
from ..models.fada_avaliacao import FadaAvaliacao
from ..models.discipline_rule import DisciplineRule
from ..models.elogio import Elogio
from ..models.ciclo import Ciclo
from ..services.notification_service import NotificationService
from sqlalchemy.orm import joinedload
import traceback

class JusticaService:
    
    @staticmethod
    def get_processos_para_usuario(user, school_id_override=None):
        try:
            # 1. Se for Aluno, vê só os dele
            if getattr(user, 'role', '') == 'aluno':
                if not getattr(user, 'aluno_profile', None): return []
                return db.session.scalars(
                    select(ProcessoDisciplina)
                    .where(ProcessoDisciplina.aluno_id == user.aluno_profile.id)
                    .order_by(ProcessoDisciplina.data_ocorrencia.desc())
                ).all()

            # 2. MODO FORÇA BRUTA (ADMIN/CAL)
            # Retorna TODOS os processos do banco, sem filtrar escola.
            # Isso serve para diagnosticar se o problema é o filtro.
            print("--- MODO DEBUG: Buscando TODOS os processos ---")
            return db.session.scalars(
                select(ProcessoDisciplina)
                .options(joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user))
                .order_by(ProcessoDisciplina.data_ocorrencia.desc())
                .limit(200) # Limite de segurança
            ).all()

        except Exception as e:
            print(f"ERRO CRÍTICO NO SERVICE: {e}")
            traceback.print_exc()
            return []

    @staticmethod
    def get_analise_disciplinar_data():
        try:
            # MODO FORÇA BRUTA: Estatísticas de TUDO que há no banco
            stats = db.session.query(ProcessoDisciplina.status, func.count(ProcessoDisciplina.id))\
                .group_by(ProcessoDisciplina.status).all()
            
            fatos = db.session.query(ProcessoDisciplina.codigo_infracao, func.count(ProcessoDisciplina.id).label('qtd'))\
                .group_by(ProcessoDisciplina.codigo_infracao).order_by(desc('qtd')).limit(5).all()
            
            fatos_fmt = []
            for cod, qtd in fatos:
                txt = "..."
                if cod:
                    r = db.session.query(DisciplineRule).filter_by(codigo=str(cod)).first()
                    if r: txt = r.descricao[:30] + "..."
                fatos_fmt.append({'codigo': cod or 'S/C', 'total': qtd, 'descricao': txt})

            alunos = db.session.query(User.nome_completo, func.count(ProcessoDisciplina.id).label('qtd'))\
                .join(Aluno).join(ProcessoDisciplina)\
                .group_by(User.nome_completo).order_by(desc('qtd')).limit(5).all()

            return {'status_counts': dict(stats), 'common_facts': fatos_fmt, 'top_alunos': [{'nome': a[0], 'total': a[1]} for a in alunos]}
        except Exception as e:
            print(f"Erro Analise: {e}")
            return {'status_counts': {}, 'common_facts': [], 'top_alunos': []}

    # --- MÉTODOS DE AÇÃO (CRIAR, FINALIZAR, ETC) MANTIDOS IGUAIS ---
    @staticmethod
    def criar_processo(descricao, observacao, aluno_id, autor_id, pontos=0.0, codigo_infracao=None, data_ocorrencia=None):
        try:
            dt = data_ocorrencia if data_ocorrencia else datetime.now().date()
            novo = ProcessoDisciplina(
                aluno_id=aluno_id, relator_id=autor_id, codigo_infracao=codigo_infracao,
                fato_constatado=descricao, observacao=observacao, pontos=pontos,
                status='Aguardando Ciência', data_ocorrencia=dt
            )
            db.session.add(novo)
            db.session.commit()
            return True, "Registrado."
        except Exception as e:
            db.session.rollback()
            return False, f"Erro: {e}"

    @staticmethod
    def finalizar_processo(pid, decisao, fundamentacao, detalhes):
        try:
            p = db.session.get(ProcessoDisciplina, pid)
            if not p: return False, "Não encontrado."
            p.status, p.decisao_final, p.fundamentacao, p.detalhes_sancao = 'Finalizado', decisao, fundamentacao, detalhes
            p.data_decisao = datetime.now()
            db.session.commit()
            return True, "Finalizado."
        except Exception as e: return False, str(e)

    @staticmethod
    def deletar_processo(pid):
        try:
            p = db.session.get(ProcessoDisciplina, pid)
            db.session.delete(p)
            db.session.commit()
            return True, "Excluído."
        except: return False, "Erro."

    @staticmethod
    def registrar_ciente(pid, user):
        try:
            p = db.session.get(ProcessoDisciplina, pid)
            p.status, p.ciente_aluno, p.data_ciente = 'Aluno Notificado', True, datetime.now()
            db.session.commit()
            return True, "Ok."
        except: return False, "Erro."

    @staticmethod
    def enviar_defesa(pid, texto, user):
        try:
            p = db.session.get(ProcessoDisciplina, pid)
            p.status, p.defesa, p.data_defesa = 'Defesa Enviada', texto, datetime.now()
            db.session.commit()
            return True, "Ok."
        except: return False, "Erro."

    # --- FADA (FORÇA BRUTA) ---
    @staticmethod
    def get_alunos_para_fada(school_id):
        # Retorna TODOS os alunos (ignora filtro complexo para teste)
        return db.session.scalars(select(Aluno).join(User).order_by(User.nome_completo).limit(100)).all()

    @staticmethod
    def calcular_previa_fada(aluno_id, ciclo_id=None):
        notas = {i: 8.0 for i in range(1, 19)}
        try:
            punicoes = db.session.scalars(select(ProcessoDisciplina).where(ProcessoDisciplina.aluno_id == aluno_id, ProcessoDisciplina.status == 'Finalizado')).all()
            for p in punicoes:
                pts = getattr(p, 'pontos', 0) or 0.0
                attr = 8
                if p.codigo_infracao:
                    try:
                        r = db.session.scalar(select(DisciplineRule).where(DisciplineRule.codigo == str(p.codigo_infracao)))
                        if r and r.atributo_fada_id: attr = r.atributo_fada_id
                    except: pass
                if 1 <= attr <= 18: notas[attr] = max(0.0, notas[attr] - float(pts))
            
            elogios = db.session.scalars(select(Elogio).where(Elogio.aluno_id == aluno_id)).all()
            for e in elogios:
                pts = e.pontos or 0.5
                if e.atributo_1: notas[e.atributo_1] = min(10.0, notas[e.atributo_1] + pts)
                if e.atributo_2: notas[e.atributo_2] = min(10.0, notas[e.atributo_2] + pts)
        except: pass
        return notas

    @staticmethod
    def salvar_fada(form_data, aluno_id, avaliador_id, nome, dados=None):
        try:
            cid = form_data.get('ciclo_id')
            av = db.session.scalar(select(FadaAvaliacao).where(FadaAvaliacao.aluno_id == aluno_id, FadaAvaliacao.ciclo_id == cid))
            if not av:
                av = FadaAvaliacao(aluno_id=aluno_id, ciclo_id=cid)
                db.session.add(av)
            
            av.avaliador_id, av.nome_avaliador_custom, av.data_avaliacao = avaliador_id, nome, datetime.now()
            
            # Mapa simples
            for i in range(1, 19):
                try: val = float(form_data.get(f'attr_{i}', 8.0))
                except: val = 8.0
                # Ajuste os nomes aqui conforme seu model REAL. 
                # Se der erro aqui, é porque os nomes no model são diferentes.
                colunas = ['attr_1_expressao', 'attr_2_planejamento', 'attr_3_perseveranca', 'attr_4_apresentacao', 'attr_5_lealdade', 'attr_6_tato', 'attr_7_equilibrio', 'attr_8_disciplina', 'attr_9_responsabilidade', 'attr_10_maturidade', 'attr_11_assiduidade', 'attr_12_pontualidade', 'attr_13_diccao', 'attr_14_lideranca', 'attr_15_relacionamento', 'attr_16_etica', 'attr_17_produtividade', 'attr_18_eficiencia']
                if i <= len(colunas): setattr(av, colunas[i-1], val)
            
            av.media_final = sum([getattr(av, c) for c in colunas]) / 18.0
            av.justificativa_notas, av.observacoes, av.adaptacao_carreira = form_data.get('justificativa_notas'), form_data.get('observacoes'), form_data.get('adaptacao_carreira')
            db.session.commit()
            return True, "Salvo!", av.id
        except Exception as e:
            db.session.rollback()
            return False, str(e), None

    @staticmethod
    def get_fada_por_id(id): return db.session.get(FadaAvaliacao, id)

    @staticmethod
    def get_processos_por_ids(ids):
        # SEM FILTRO DE ESCOLA
        return db.session.scalars(select(ProcessoDisciplina).where(ProcessoDisciplina.id.in_(ids))).all()

    @staticmethod
    def get_finalized_processos():
        # SEM FILTRO DE ESCOLA
        return db.session.scalars(select(ProcessoDisciplina).where(ProcessoDisciplina.status == 'Finalizado').order_by(ProcessoDisciplina.data_decisao.desc())).all()