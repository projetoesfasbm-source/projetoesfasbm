from flask import g, url_for, session
from ..services.email_service import EmailService
from sqlalchemy import select, func, desc
from datetime import datetime, timezone
from ..models.database import db
from ..models.aluno import Aluno
from ..models.user import User
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
        """Busca processos relevantes com base no perfil."""
        if getattr(user, 'is_cal', False) or getattr(user, 'is_admin_escola', False) or getattr(user, 'is_programador', False) or getattr(user, 'role', '') == 'super_admin':
            
            school_id_to_load = None
            if user.role in ['super_admin', 'programador']:
                school_id_to_load = session.get('view_as_school_id')
            
            if not school_id_to_load:
                if hasattr(user, 'temp_active_school_id'):
                    school_id_to_load = user.temp_active_school_id
                elif session.get('active_school_id'):
                    school_id_to_load = int(session.get('active_school_id'))

            if not school_id_to_load: return [] 
            
            query = (
                select(ProcessoDisciplina)
                .join(Aluno, ProcessoDisciplina.aluno_id == Aluno.id)
                .join(User, Aluno.user_id == User.id)
                .join(UserSchool, User.id == UserSchool.user_id) 
                .where(UserSchool.school_id == school_id_to_load) 
                .options(joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user), joinedload(ProcessoDisciplina.relator))
                .distinct()
                .order_by(ProcessoDisciplina.data_ocorrencia.desc())
            )
            return db.session.scalars(query).all()
        else:
            if not getattr(user, 'aluno_profile', None): return [] 
            return db.session.scalars(
                select(ProcessoDisciplina)
                .where(ProcessoDisciplina.aluno_id == user.aluno_profile.id)
                .options(joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user))
                .order_by(ProcessoDisciplina.data_ocorrencia.desc())
            ).all()

    @staticmethod
    def criar_processo(descricao, observacao, aluno_id, autor_id, pontos=0.0, codigo_infracao=None, data_ocorrencia=None):
        try:
            dt_ocorrencia = data_ocorrencia if data_ocorrencia else datetime.now().date()
            novo = ProcessoDisciplina(
                aluno_id=aluno_id,
                relator_id=autor_id,
                codigo_infracao=codigo_infracao,
                fato_constatado=descricao,
                observacao=observacao,
                pontos=pontos,
                status='Aguardando Ciência',
                data_ocorrencia=dt_ocorrencia
            )
            db.session.add(novo)
            db.session.commit()
            
            # Notificação simplificada
            aluno = db.session.get(Aluno, aluno_id)
            if aluno and aluno.user:
                NotificationService.create_notification(
                    user_id=aluno.user.id,
                    message=f"Novo Processo: {descricao[:30]}...", 
                    url=url_for('justica.index', _external=True)
                )
            return True, "Registrado."
        except Exception as e:
            db.session.rollback()
            return False, f"Erro: {str(e)}"

    @staticmethod
    def finalizar_processo(pid, decisao, fundamentacao, detalhes):
        proc = db.session.get(ProcessoDisciplina, pid)
        if not proc: return False, "Não encontrado."
        proc.status, proc.decisao_final, proc.fundamentacao, proc.detalhes_sancao = 'Finalizado', decisao, fundamentacao, detalhes
        proc.data_decisao = datetime.now()
        db.session.commit()
        return True, "Finalizado."

    @staticmethod
    def deletar_processo(pid):
        proc = db.session.get(ProcessoDisciplina, pid)
        if not proc: return False, "Não encontrado."
        db.session.delete(proc)
        db.session.commit()
        return True, "Excluído."

    @staticmethod
    def registrar_ciente(pid, user):
        proc = db.session.get(ProcessoDisciplina, pid)
        if not proc: return False, "Erro."
        proc.status, proc.ciente_aluno, proc.data_ciente = 'Aluno Notificado', True, datetime.now()
        db.session.commit()
        return True, "Ciente ok."

    @staticmethod
    def enviar_defesa(pid, texto, user):
        proc = db.session.get(ProcessoDisciplina, pid)
        if not proc: return False, "Erro."
        proc.status, proc.defesa, proc.data_defesa = 'Defesa Enviada', texto, datetime.now()
        db.session.commit()
        return True, "Defesa ok."

    # --- FADA ---
    @staticmethod
    def get_alunos_para_fada(school_id):
        return db.session.scalars(select(Aluno).join(User).join(UserSchool).where(UserSchool.school_id == school_id, User.role == 'aluno').order_by(User.nome_completo)).all()

    @staticmethod
    def calcular_previa_fada(aluno_id, ciclo_id=None):
        notas = {i: 8.0 for i in range(1, 19)}
        # Filtra punições finalizadas
        for p in db.session.scalars(select(ProcessoDisciplina).where(ProcessoDisciplina.aluno_id == aluno_id, ProcessoDisciplina.status == 'Finalizado')).all():
            pts, codigo = getattr(p, 'pontos', 0) or 0.0, getattr(p, 'codigo_infracao', None)
            attr = 8 # Padrão Disciplina
            if codigo:
                regra = db.session.scalar(select(DisciplineRule).where(DisciplineRule.codigo == codigo))
                if regra and regra.atributo_fada_id: attr = regra.atributo_fada_id
            notas[attr] = max(0.0, notas[attr] - float(pts))
        
        # Filtra elogios
        for e in db.session.scalars(select(Elogio).where(Elogio.aluno_id == aluno_id)).all():
            pts = e.pontos or 0.5
            if e.atributo_1: notas[e.atributo_1] = min(10.0, notas[e.atributo_1] + pts)
            if e.atributo_2: notas[e.atributo_2] = min(10.0, notas[e.atributo_2] + pts)
        return notas

    @staticmethod
    def salvar_fada(form_data, aluno_id, avaliador_id, nome_avaliador, dados_calculados=None):
        try:
            cid = form_data.get('ciclo_id')
            av = db.session.scalar(select(FadaAvaliacao).where(FadaAvaliacao.aluno_id == aluno_id, FadaAvaliacao.ciclo_id == cid))
            if not av:
                av = FadaAvaliacao(aluno_id=aluno_id, ciclo_id=cid)
                db.session.add(av)
            
            av.avaliador_id, av.nome_avaliador_custom, av.data_avaliacao = avaliador_id, nome_avaliador, datetime.now()
            
            total = 0
            mapa = ['attr_1_expressao', 'attr_2_planejamento', 'attr_3_perseveranca', 'attr_4_apresentacao', 'attr_5_lealdade', 'attr_6_tato', 'attr_7_equilibrio', 'attr_8_disciplina', 'attr_9_responsabilidade', 'attr_10_maturidade', 'attr_11_assiduidade', 'attr_12_pontualidade', 'attr_13_diccao', 'attr_14_lideranca', 'attr_15_relacionamento', 'attr_16_etica', 'attr_17_produtividade', 'attr_18_eficiencia']
            for i, c in enumerate(mapa, 1):
                val = float(form_data.get(f'attr_{i}', 8.0))
                setattr(av, c, val)
                total += val
            
            av.media_final = total / 18.0
            av.justificativa_notas, av.observacoes, av.adaptacao_carreira = form_data.get('justificativa_notas'), form_data.get('observacoes'), form_data.get('adaptacao_carreira')
            db.session.commit()
            return True, "Salvo com sucesso!", av.id
        except Exception as e:
            db.session.rollback()
            return False, f"Erro: {e}", None

    @staticmethod
    def get_fada_por_id(id): return db.session.get(FadaAvaliacao, id)

    # --- ANÁLISE FILTRADA POR ESCOLA (CORREÇÃO DO VAZAMENTO DE DADOS) ---
    @staticmethod
    def get_analise_disciplinar_data():
        active_school = g.get('active_school')
        if not active_school: return {'status_counts': {}, 'common_facts': [], 'top_alunos': []}

        # Subquery para filtrar alunos DA ESCOLA ATIVA
        subquery = select(Aluno.id).join(User).join(UserSchool).where(UserSchool.school_id == active_school.id, User.role == 'aluno')

        # Estatísticas filtradas
        stats = db.session.query(ProcessoDisciplina.status, func.count(ProcessoDisciplina.id))\
            .filter(ProcessoDisciplina.aluno_id.in_(subquery))\
            .group_by(ProcessoDisciplina.status).all()
        
        fatos = db.session.query(ProcessoDisciplina.codigo_infracao, func.count(ProcessoDisciplina.id).label('qtd'))\
            .filter(ProcessoDisciplina.aluno_id.in_(subquery))\
            .group_by(ProcessoDisciplina.codigo_infracao).order_by(desc('qtd')).limit(5).all()
        
        # Recupera descrição da regra se possível
        fatos_formatados = []
        for cod, qtd in fatos:
            desc_texto = "..."
            if cod:
                r = db.session.query(DisciplineRule).filter_by(codigo=str(cod)).first()
                if r: desc_texto = r.descricao[:30] + "..."
            fatos_formatados.append({'codigo': cod or 'S/C', 'total': qtd, 'descricao': desc_texto})

        alunos = db.session.query(User.nome_completo, func.count(ProcessoDisciplina.id).label('qtd'))\
            .join(Aluno).join(ProcessoDisciplina).filter(ProcessoDisciplina.aluno_id.in_(subquery))\
            .group_by(User.nome_completo).order_by(desc('qtd')).limit(5).all()

        return {
            'status_counts': dict(stats), 
            'common_facts': fatos_formatados,
            'top_alunos': [{'nome': a[0], 'total': a[1]} for a in alunos]
        }
    
    @staticmethod
    def get_processos_por_ids(ids): return db.session.scalars(select(ProcessoDisciplina).where(ProcessoDisciplina.id.in_(ids))).all()
    
    @staticmethod
    def get_finalized_processos(): return db.session.scalars(select(ProcessoDisciplina).where(ProcessoDisciplina.status == 'Finalizado')).all()