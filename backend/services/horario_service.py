# backend/services/horario_service.py

from flask import current_app, url_for
from flask_login import current_user
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import joinedload
from datetime import date, timedelta
from collections import defaultdict
import uuid

from ..models.database import db
from ..models.horario import Horario
from ..models.disciplina import Disciplina
from ..models.instrutor import Instrutor
from ..models.disciplina_turma import DisciplinaTurma
from ..models.semana import Semana
from ..models.turma import Turma
from ..models.user import User
from .notification_service import NotificationService 


class HorarioService:

    @staticmethod
    def can_edit_horario(horario, user):
        if not horario or not user:
            return False
        if user.role in ['super_admin', 'programador', 'admin_escola']:
            return True
        if user.role == 'instrutor' and user.instrutor_profile:
            instrutor_id = user.instrutor_profile.id
            return horario.instrutor_id == instrutor_id or horario.instrutor_id_2 == instrutor_id
        return False

    @staticmethod
    def construir_matriz_horario(pelotao, semana_id, user):
        a_disposicao = {'materia': 'A disposição do C Al /S Ens', 'instrutor': None, 'duracao': 1, 'is_disposicao': True, 'id': None, 'status': 'confirmado'}
        horario_matrix = [[dict(a_disposicao) for _ in range(7)] for _ in range(15)]
        dias = ['segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado', 'domingo']
        
        aulas_query = select(Horario).options(
            joinedload(Horario.disciplina),
            joinedload(Horario.instrutor).joinedload(Instrutor.user),
            joinedload(Horario.instrutor_2).joinedload(Instrutor.user)
        ).where(Horario.pelotao == pelotao, Horario.semana_id == semana_id)
        
        all_aulas = db.session.scalars(aulas_query).all()

        for aula in all_aulas:
            try:
                dia_idx = dias.index(aula.dia_semana)
                periodo_idx = aula.periodo - 1

                can_see_pending_details = HorarioService.can_edit_horario(aula, user)
                show_details = aula.status == 'confirmado' or can_see_pending_details
                
                instrutores_display_list = []
                if aula.instrutor and aula.instrutor.user:
                    nome = aula.instrutor.user.nome_de_guerra or aula.instrutor.user.username
                    instrutores_display_list.append(nome)
                if aula.instrutor_2 and aula.instrutor_2.user:
                    nome = aula.instrutor_2.user.nome_de_guerra or aula.instrutor_2.user.username
                    instrutores_display_list.append(nome)
                instrutor_display = " / ".join(instrutores_display_list) if instrutores_display_list else "N/D"

                aula_info = {
                    'id': aula.id, 'materia': aula.disciplina.materia if show_details else 'Aguardando Aprovação',
                    'instrutor': instrutor_display if show_details else None, 'observacao': aula.observacao,
                    'duracao': aula.duracao, 'status': aula.status, 'is_disposicao': False,
                    'can_edit': HorarioService.can_edit_horario(aula, user), 'is_continuation': False,
                    'group_id': aula.group_id
                }
                
                if 0 <= periodo_idx < 15:
                    horario_matrix[periodo_idx][dia_idx] = aula_info
                    for i in range(1, aula.duracao):
                        if (periodo_idx + i) < 15:
                            horario_matrix[periodo_idx + i][dia_idx] = 'SKIP'
            except (ValueError, IndexError):
                continue
        return horario_matrix

    @staticmethod
    def get_semana_selecionada(semana_id_str, ciclo_id):
        if semana_id_str and semana_id_str.isdigit():
            return db.session.get(Semana, int(semana_id_str))
        
        today = date.today()
        semana_atual = db.session.scalars(select(Semana).where(Semana.ciclo_id == ciclo_id, Semana.data_inicio <= today, Semana.data_fim >= today)).first()
        if semana_atual: return semana_atual
            
        return db.session.scalars(select(Semana).where(Semana.ciclo_id == ciclo_id).order_by(Semana.data_inicio.desc())).first()

    @staticmethod
    def get_datas_da_semana(semana):
        if not semana: return {}
        datas = {}
        dias = ['segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado', 'domingo']
        for i, dia_nome in enumerate(dias):
            datas[dia_nome] = (semana.data_inicio + timedelta(days=i)).strftime('%d/%m')
        return datas

    @staticmethod
    def get_edit_grid_context(pelotao, semana_id, ciclo_id, user):
        horario_matrix = HorarioService.construir_matriz_horario(pelotao, semana_id, user)
        semana = db.session.get(Semana, semana_id)
        is_admin = user.role in ['super_admin', 'programador', 'admin_escola']
        
        def get_horas_agendadas(disciplina_id, pelotao_nome):
            return db.session.scalar(select(func.sum(Horario.duracao)).where(Horario.disciplina_id == disciplina_id, Horario.pelotao == pelotao_nome)) or 0

        turma_obj = db.session.scalar(select(Turma).where(Turma.nome == pelotao))
        if not turma_obj: return {'success': False, 'message': 'Turma não encontrada.'}

        disciplinas_disponiveis = []
        if is_admin:
            disciplinas_da_turma = db.session.scalars(select(Disciplina).where(Disciplina.turma_id == turma_obj.id).order_by(Disciplina.materia)).all()
            for d in disciplinas_da_turma:
                horas_restantes = d.carga_horaria_prevista - get_horas_agendadas(d.id, pelotao)
                disciplinas_disponiveis.append({"id": d.id, "nome": d.materia, "restantes": horas_restantes})
        else:
            instrutor_id = user.instrutor_profile.id if user.instrutor_profile else 0
            disciplinas_do_instrutor = db.session.scalars(select(Disciplina).join(DisciplinaTurma, Disciplina.id == DisciplinaTurma.disciplina_id).where(Disciplina.turma_id == turma_obj.id, or_(DisciplinaTurma.instrutor_id_1 == instrutor_id, DisciplinaTurma.instrutor_id_2 == instrutor_id)).order_by(Disciplina.materia)).all()
            for d in disciplinas_do_instrutor:
                horas_restantes = d.carga_horaria_prevista - get_horas_agendadas(d.id, pelotao)
                disciplinas_disponiveis.append({"id": d.id, "nome": d.materia, "restantes": horas_restantes})

        todos_instrutores = [{"id": i.id, "nome": i.user.nome_de_guerra or i.user.username} for i in db.session.scalars(select(Instrutor).options(joinedload(Instrutor.user)).join(User).order_by(User.nome_de_guerra)).all()]

        return {
            'success': True, 'horario_matrix': horario_matrix, 'pelotao_selecionado': pelotao,
            'semana_selecionada': semana, 'disciplinas_disponiveis': disciplinas_disponiveis,
            'todos_instrutores': todos_instrutores, 'is_admin': is_admin,
            'instrutor_logado_id': user.instrutor_profile.id if user.instrutor_profile else None,
            'datas_semana': HorarioService.get_datas_da_semana(semana)
        }

    @staticmethod
    def get_aula_details(horario_id, user):
        aula = db.session.get(Horario, horario_id)
        if not aula or not HorarioService.can_edit_horario(aula, user): return None
        
        duracao_total = aula.duracao
        if aula.group_id:
            duracao_total = db.session.scalar(select(func.sum(Horario.duracao)).where(Horario.group_id == aula.group_id))

        instrutor_value = str(aula.instrutor_id)
        if aula.instrutor_id_2:
            instrutor_value = f"{aula.instrutor_id}-{aula.instrutor_id_2}"

        return {
            'disciplina_id': aula.disciplina_id, 'instrutor_value': instrutor_value,
            'duracao': duracao_total, 'observacao': aula.observacao, 'periodo': aula.periodo,
            'materia': aula.disciplina.materia,
            'instrutor_nome': (aula.instrutor.user.nome_de_guerra if aula.instrutor and aula.instrutor.user else '')
        }

    @staticmethod
    def save_aula(data, user):
        try:
            horario_id_raw = data.get('horario_id')
            horario_id = int(horario_id_raw) if horario_id_raw else None
            pelotao, semana_id, dia = data['pelotao'], int(data['semana_id']), data['dia']
            periodo_inicio, duracao = int(data['periodo']), int(data.get('duracao', 1))
            periodo_fim = periodo_inicio + duracao - 1
            observacao = data.get('observacao', '').strip() or None
            is_admin = user.role in ['super_admin', 'programador', 'admin_escola']
            disciplina_id = int(data['disciplina_id'])

            instrutor_id_1, instrutor_id_2 = None, None
            if is_admin:
                instrutor_id_from_form = data.get('instrutor_id', '')
                if not instrutor_id_from_form: return False, 'Como administrador, você deve selecionar um instrutor.', 400
                if '-' in instrutor_id_from_form:
                    id1, id2 = instrutor_id_from_form.split('-')
                    instrutor_id_1, instrutor_id_2 = int(id1), int(id2)
                else: instrutor_id_1 = int(instrutor_id_from_form)
            else:
                if not user.instrutor_profile: return False, 'O seu perfil de instrutor não foi encontrado.', 403
                instrutor_id_1 = user.instrutor_profile.id
            if not instrutor_id_1: return False, 'Instrutor principal não especificado.', 400
            
            if horario_id:
                aula_original = db.session.get(Horario, horario_id)
                if not aula_original or not HorarioService.can_edit_horario(aula_original, user): return False, 'Aula não encontrada ou sem permissão para editar.', 404
                if aula_original.group_id: db.session.query(Horario).filter(Horario.group_id == aula_original.group_id).delete()
                else: db.session.delete(aula_original)
                db.session.flush()

            break_points = {3, 6, 9}
            group_id = str(uuid.uuid4()) if duracao > 1 else None
            periodos_restantes = list(range(periodo_inicio, periodo_fim + 1))
            
            while periodos_restantes:
                periodo_bloco_inicio = periodos_restantes[0]
                periodo_bloco_fim = periodo_bloco_inicio
                for i in range(1, len(periodos_restantes)):
                    if periodos_restantes[i] == periodo_bloco_fim + 1 and periodo_bloco_fim not in break_points:
                        periodo_bloco_fim = periodos_restantes[i]
                    else: break
                duracao_bloco = (periodo_bloco_fim - periodo_bloco_inicio) + 1

                query_conflito = select(Horario).where(Horario.pelotao == pelotao, Horario.semana_id == semana_id, Horario.dia_semana == dia, Horario.periodo <= periodo_bloco_fim, (Horario.periodo + Horario.duracao - 1) >= periodo_bloco_inicio)
                if db.session.execute(query_conflito).scalars().first(): return False, f'Conflito de horário no período {periodo_bloco_inicio}.', 409

                nova_aula_bloco = Horario(
                    pelotao=pelotao, semana_id=semana_id, dia_semana=dia, periodo=periodo_bloco_inicio, duracao=duracao_bloco,
                    disciplina_id=disciplina_id, observacao=observacao, instrutor_id=instrutor_id_1, instrutor_id_2=instrutor_id_2,
                    status='confirmado' if is_admin else 'pendente', group_id=group_id
                )
                db.session.add(nova_aula_bloco)
                periodos_restantes = periodos_restantes[duracao_bloco:]

            if not is_admin:
                disciplina = db.session.get(Disciplina, disciplina_id)
                turma = db.session.scalar(select(Turma).where(Turma.nome == pelotao))
                if turma and turma.school_id:
                    message = f"O instrutor {user.nome_de_guerra} agendou uma nova aula de {disciplina.materia} que precisa de aprovação."
                    notification_url = url_for('horario.aprovar_horarios', _external=True)
                    NotificationService.create_notification_for_roles(turma.school_id, ['admin_escola', 'super_admin', 'programador'], message, notification_url)

            db.session.commit()
            return True, 'Aula salva com sucesso!', 200
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao salvar aula: {e}")
            return False, 'Erro interno do servidor ao salvar.', 500

    @staticmethod
    def remove_aula(horario_id, user):
        aula = db.session.get(Horario, int(horario_id))
        if not aula or not HorarioService.can_edit_horario(aula, user): return False, 'Aula não encontrada ou sem permissão.'
        
        if aula.group_id: db.session.query(Horario).filter(Horario.group_id == aula.group_id).delete()
        else: db.session.delete(aula)
        
        db.session.commit()
        return True, 'Aula removida com sucesso!'

    # ... (Restante do serviço sem alterações) ...
    @staticmethod
    def get_aulas_pendentes():
        return db.session.scalars(select(Horario).options(joinedload(Horario.disciplina).joinedload(Disciplina.ciclo), joinedload(Horario.instrutor).joinedload(Instrutor.user), joinedload(Horario.semana)).where(Horario.status == 'pendente').order_by(Horario.id.desc())).all()
        
    @staticmethod
    def aprovar_horario(horario_id, action):
        aula = db.session.get(Horario, int(horario_id))
        if not aula: return False, 'Aula não encontrada.'
        instrutor_user_id = aula.instrutor.user_id if aula.instrutor else None
        
        if action == 'aprovar':
            aula.status = 'confirmado'
            message = f'Aula de {aula.disciplina.materia} aprovada.'
            turma = db.session.scalar(select(Turma).where(Turma.nome == aula.pelotao))
            if turma:
                notif_url = url_for('horario.index', pelotao=turma.nome, semana_id=aula.semana_id, _external=True)
                if instrutor_user_id: NotificationService.create_notification(instrutor_user_id, f"Sua aula de {aula.disciplina.materia} para a turma {turma.nome} foi aprovada.", notif_url)
                for aluno in turma.alunos: NotificationService.create_notification(aluno.user_id, f"Nova aula de {aula.disciplina.materia} agendada para sua turma.", notif_url)
        elif action == 'negar':
            db.session.delete(aula)
            message = f'Solicitação de aula de {aula.disciplina.materia} foi negada e removida.'
        else: return False, 'Ação inválida.'
        db.session.commit()
        return True, message

    @staticmethod
    def _group_consecutive_periods(periods):
        if not periods: return []
        sorted_periods = sorted(periods)
        groups, current_group_start = [], sorted_periods[0]
        for i in range(1, len(sorted_periods)):
            if sorted_periods[i] != sorted_periods[i-1] + 1:
                groups.append((current_group_start, sorted_periods[i-1]))
                current_group_start = sorted_periods[i]
        groups.append((current_group_start, sorted_periods[-1]))
        return groups

    @staticmethod
    def aprovar_horario_parcialmente(horario_id, periodos_para_aprovar):
        aula_pendente = db.session.get(Horario, horario_id)
        if not aula_pendente or aula_pendente.status != 'pendente': return False, "Aula pendente não encontrada."
        instrutor_user_id = aula_pendente.instrutor.user_id if aula_pendente.instrutor else None
        turma = db.session.scalar(select(Turma).where(Turma.nome == aula_pendente.pelotao))
        notif_url = url_for('horario.index', pelotao=aula_pendente.pelotao, semana_id=aula_pendente.semana_id, _external=True)
        
        try:
            if not periodos_para_aprovar:
                db.session.delete(aula_pendente)
                if instrutor_user_id: NotificationService.create_notification(instrutor_user_id, f"Sua solicitação de aula de {aula_pendente.disciplina.materia} foi negada.", notif_url)
                db.session.commit()
                return True, "Aula negada com sucesso."

            todos_periodos_originais = set(range(aula_pendente.periodo, aula_pendente.periodo + aula_pendente.duracao))
            if set(periodos_para_aprovar) == todos_periodos_originais:
                aula_pendente.status = 'confirmado'
                message, notif_msg_instrutor, notif_msg_alunos = "Aula aprovada com sucesso.", f"Sua aula de {aula_pendente.disciplina.materia} foi aprovada.", f"Nova aula de {aula_pendente.disciplina.materia} agendada."
            else:
                db.session.delete(aula_pendente)
                for grupo_inicio, grupo_fim in HorarioService._group_consecutive_periods(periodos_para_aprovar):
                    nova_aula = Horario(pelotao=aula_pendente.pelotao, dia_semana=aula_pendente.dia_semana, periodo=grupo_inicio, duracao=(grupo_fim - grupo_inicio + 1), semana_id=aula_pendente.semana_id, disciplina_id=aula_pendente.disciplina_id, instrutor_id=aula_pendente.instrutor_id, instrutor_id_2=aula_pendente.instrutor_id_2, observacao=aula_pendente.observacao, status='confirmado')
                    db.session.add(nova_aula)
                message, notif_msg_instrutor, notif_msg_alunos = "Aula parcialmente aprovada com sucesso.", f"Sua aula de {aula_pendente.disciplina.materia} foi aprovada parcialmente.", f"Nova aula de {aula_pendente.disciplina.materia} agendada (parcialmente)."
            
            if instrutor_user_id: NotificationService.create_notification(instrutor_user_id, notif_msg_instrutor, notif_url)
            if turma:
                for aluno in turma.alunos: NotificationService.create_notification(aluno.user_id, notif_msg_alunos, notif_url)
            
            db.session.commit()
            return True, message
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro na aprovação parcial: {e}")
            return False, "Ocorreu um erro ao processar a aprovação."