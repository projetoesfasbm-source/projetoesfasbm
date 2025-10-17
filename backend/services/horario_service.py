# backend/services/horario_service.py

from flask import current_app, url_for
from flask_login import current_user
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import joinedload
from datetime import date, timedelta
from collections import defaultdict

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
    def _group_consecutive_periods(periods):
        if not periods:
            return []
        sorted_periods = sorted(periods)
        groups = []
        current_group_start = sorted_periods[0]
        for i in range(1, len(sorted_periods)):
            if sorted_periods[i] != sorted_periods[i-1] + 1:
                groups.append((current_group_start, sorted_periods[i-1]))
                current_group_start = sorted_periods[i]
        groups.append((current_group_start, sorted_periods[-1]))
        return groups

    @staticmethod
    def construir_matriz_horario(pelotao, semana_id, user):
        a_disposicao = {'materia': 'A disposição do C Al /S Ens', 'instrutor': None, 'duracao': 1, 'is_disposicao': True, 'id': None, 'status': 'confirmado'}
        horario_matrix = [[dict(a_disposicao) for _ in range(7)] for _ in range(15)]
        dias = ['segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado', 'domingo']
        
        aulas_query = select(Horario).options(
            joinedload(Horario.disciplina),
            joinedload(Horario.instrutor).joinedload(Instrutor.user),
            joinedload(Horario.instrutor_2).joinedload(Instrutor.user)
        ).where(Horario.pelotao == pelotao, Horario.semana_id == semana_id).order_by(Horario.dia_semana, Horario.periodo)
        
        all_aulas_originais = db.session.scalars(aulas_query).all()

        # --- NOVA LÓGICA DE MESCLAGEM DE AULAS SEQUENCIAIS ---
        aulas_processadas = []
        if all_aulas_originais:
            # Dicionário para agrupar aulas por dia
            aulas_por_dia = defaultdict(list)
            for aula in all_aulas_originais:
                aulas_por_dia[aula.dia_semana].append(aula)

            merged_aulas_final = []
            for dia in dias:
                if dia in aulas_por_dia:
                    aulas_do_dia = sorted(aulas_por_dia[dia], key=lambda a: a.periodo)
                    
                    if not aulas_do_dia: continue

                    bloco_mesclado = aulas_do_dia[0]
                    for i in range(1, len(aulas_do_dia)):
                        aula_atual = aulas_do_dia[i]
                        
                        # Condições para mesclar
                        e_sequencial = (aula_atual.periodo == (bloco_mesclado.periodo + bloco_mesclado.duracao))
                        e_identica = (
                            aula_atual.disciplina_id == bloco_mesclado.disciplina_id and
                            aula_atual.instrutor_id == bloco_mesclado.instrutor_id and
                            aula_atual.instrutor_id_2 == bloco_mesclado.instrutor_id_2 and
                            aula_atual.status == bloco_mesclado.status and
                            aula_atual.observacao == bloco_mesclado.observacao
                        )

                        if e_sequencial and e_identica:
                            # Mescla a aula atual no bloco, somando a duração
                            bloco_mesclado.duracao += aula_atual.duracao
                        else:
                            # Finaliza o bloco anterior e começa um novo
                            merged_aulas_final.append(bloco_mesclado)
                            bloco_mesclado = aula_atual
                    
                    # Adiciona o último bloco processado
                    merged_aulas_final.append(bloco_mesclado)
            aulas_processadas = merged_aulas_final
        # --- FIM DA LÓGICA DE MESCLAGEM ---

        for aula in aulas_processadas: # <-- Usa a lista de aulas já mescladas
            try:
                dia_idx = dias.index(aula.dia_semana)
                
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
                    'id': aula.id,
                    'materia': aula.disciplina.materia if show_details else 'Aguardando Aprovação',
                    'instrutor': instrutor_display if show_details else None,
                    'observacao': aula.observacao,
                    'duracao': aula.duracao,
                    'status': aula.status,
                    'is_disposicao': False,
                    'can_edit': HorarioService.can_edit_horario(aula, user),
                    'is_continuation': False # Esta lógica de continuação não é mais necessária com a mesclagem
                }
                
                periodo_idx = aula.periodo - 1
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
        semana_atual = db.session.scalars(
            select(Semana).where(
                Semana.ciclo_id == ciclo_id,
                Semana.data_inicio <= today,
                Semana.data_fim >= today
            )
        ).first()
        if semana_atual:
            return semana_atual
            
        return db.session.scalars(
            select(Semana).where(Semana.ciclo_id == ciclo_id).order_by(Semana.data_inicio.desc())
        ).first()

    @staticmethod
    def get_datas_da_semana(semana):
        if not semana:
            return {}
        datas = {}
        dias = ['segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado', 'domingo']
        for i, dia_nome in enumerate(dias):
            data_calculada = semana.data_inicio + timedelta(days=i)
            datas[dia_nome] = data_calculada.strftime('%d/%m')
        return datas

    @staticmethod
    def get_edit_grid_context(pelotao, semana_id, ciclo_id, user):
        horario_matrix = HorarioService.construir_matriz_horario(pelotao, semana_id, user)
        semana = db.session.get(Semana, semana_id)
        is_admin = user.role in ['super_admin', 'programador', 'admin_escola']
        
        def get_horas_agendadas(disciplina_id, pelotao_nome):
            total_agendado = db.session.scalar(
                select(func.sum(Horario.duracao)).where(
                    Horario.disciplina_id == disciplina_id,
                    Horario.pelotao == pelotao_nome
                )
            )
            return total_agendado or 0

        disciplinas_disponiveis = []
        
        turma_obj = db.session.scalar(select(Turma).where(Turma.nome == pelotao))
        if not turma_obj:
            return {'success': False, 'message': 'Turma não encontrada.'}

        if is_admin:
            disciplinas_da_turma = db.session.scalars(
                select(Disciplina).where(Disciplina.turma_id == turma_obj.id).order_by(Disciplina.materia)
            ).all()
            for d in disciplinas_da_turma:
                horas_agendadas = get_horas_agendadas(d.id, pelotao)
                horas_restantes = d.carga_horaria_prevista - horas_agendadas
                disciplinas_disponiveis.append({"id": d.id, "nome": d.materia, "restantes": horas_restantes})
        else:
            instrutor_id = user.instrutor_profile.id if user.instrutor_profile else 0
            disciplinas_do_instrutor = db.session.scalars(
                select(Disciplina)
                .join(DisciplinaTurma, Disciplina.id == DisciplinaTurma.disciplina_id)
                .where(
                    Disciplina.turma_id == turma_obj.id,
                    (DisciplinaTurma.instrutor_id_1 == instrutor_id) | (DisciplinaTurma.instrutor_id_2 == instrutor_id)
                )
                .order_by(Disciplina.materia)
            ).all()

            for d in disciplinas_do_instrutor:
                horas_agendadas = get_horas_agendadas(d.id, pelotao)
                horas_restantes = d.carga_horaria_prevista - horas_agendadas
                disciplinas_disponiveis.append({"id": d.id, "nome": d.materia, "restantes": horas_restantes})

        todos_instrutores = [{"id": i.id, "nome": i.user.nome_de_guerra or i.user.username} for i in db.session.scalars(select(Instrutor).options(joinedload(Instrutor.user)).join(User).order_by(User.nome_de_guerra)).all()]

        return {
            'success': True,
            'horario_matrix': horario_matrix,
            'pelotao_selecionado': pelotao,
            'semana_selecionada': semana,
            'disciplinas_disponiveis': disciplinas_disponiveis,
            'todos_instrutores': todos_instrutores,
            'is_admin': is_admin,
            'instrutor_logado_id': user.instrutor_profile.id if user.instrutor_profile else None,
            'datas_semana': HorarioService.get_datas_da_semana(semana)
        }

    @staticmethod
    def get_aula_details(horario_id, user):
        aula = db.session.get(Horario, horario_id)
        if not aula or not HorarioService.can_edit_horario(aula, user):
            return None
            
        instrutor_value = str(aula.instrutor_id)
        if aula.instrutor_id_2:
            instrutor_value = f"{aula.instrutor_id}-{aula.instrutor_id_2}"

        return {
            'disciplina_id': aula.disciplina_id,
            'instrutor_value': instrutor_value,
            'duracao': aula.duracao,
            'observacao': aula.observacao,
            'periodo': aula.periodo,
            'materia': aula.disciplina.materia,
            'instrutor_nome': (aula.instrutor.user.nome_de_guerra if aula.instrutor and aula.instrutor.user else '')
        }

    @staticmethod
    def save_aula(data, user):
        try:
            horario_id_raw = data.get('horario_id')
            horario_id = int(horario_id_raw) if horario_id_raw else None
            
            pelotao = data['pelotao']
            semana_id = int(data['semana_id'])
            dia = data['dia']
            periodo_inicio = int(data['periodo'])
            duracao = int(data.get('duracao', 1))
            periodo_fim = periodo_inicio + duracao - 1
            observacao = data.get('observacao', '').strip() or None
            is_admin = user.role in ['super_admin', 'programador', 'admin_escola']
            disciplina_id = int(data['disciplina_id'])

            semana = db.session.get(Semana, semana_id)
            if not semana:
                return False, 'Semana não encontrada.', 404
            
            max_periodo = 12
            if dia == 'sabado' and semana.mostrar_sabado: max_periodo = semana.periodos_sabado
            elif dia == 'domingo' and semana.mostrar_domingo: max_periodo = semana.periodos_domingo
            elif dia not in ['sabado', 'domingo']:
                if semana.mostrar_periodo_15: max_periodo = 15
                elif semana.mostrar_periodo_14: max_periodo = 14
                elif semana.mostrar_periodo_13: max_periodo = 13

            if periodo_fim > max_periodo:
                return False, f'A duração da aula ultrapassa o último período permitido ({max_periodo}º) para este dia.', 400

            query_conflito = select(Horario).where(
                Horario.pelotao == pelotao,
                Horario.semana_id == semana_id,
                Horario.dia_semana == dia,
                Horario.periodo <= periodo_fim,
                (Horario.periodo + Horario.duracao - 1) >= periodo_inicio
            )
            if horario_id:
                query_conflito = query_conflito.where(Horario.id != horario_id)
            
            conflito_existente = db.session.execute(query_conflito).scalars().first()
            if conflito_existente:
                return False, f'Conflito de horário. Já existe uma aula de "{conflito_existente.disciplina.materia}" que ocupa o {conflito_existente.periodo}º período.', 409

            disciplina = db.session.get(Disciplina, disciplina_id)
            if not disciplina:
                return False, 'Disciplina não encontrada.', 404
                
            total_agendado_outras_aulas = db.session.scalar(
                select(func.sum(Horario.duracao)).where(
                    Horario.disciplina_id == disciplina_id,
                    Horario.pelotao == pelotao,
                    (Horario.id != horario_id) if horario_id else True
                )
            ) or 0
            
            horas_restantes = disciplina.carga_horaria_prevista - total_agendado_outras_aulas
            if duracao > horas_restantes:
                return False, f'Não é possível agendar {duracao}h. Apenas {horas_restantes}h restam para esta disciplina.', 400

            instrutor_id_1, instrutor_id_2 = None, None
            if is_admin:
                instrutor_id_from_form = data.get('instrutor_id', '')
                if not instrutor_id_from_form:
                    return False, 'Como administrador, você deve selecionar um instrutor.', 400
                if '-' in instrutor_id_from_form:
                    id1, id2 = instrutor_id_from_form.split('-')
                    instrutor_id_1, instrutor_id_2 = int(id1), int(id2)
                else:
                    instrutor_id_1 = int(instrutor_id_from_form)
            else:
                if not user.instrutor_profile:
                    return False, 'O seu perfil de instrutor não foi encontrado.', 403
                instrutor_id_1 = user.instrutor_profile.id

            if not instrutor_id_1:
                return False, 'Instrutor principal não especificado.', 400

        except (KeyError, ValueError, TypeError):
            return False, 'Dados inválidos ou incompletos.', 400

        is_new_aula = not horario_id
        if horario_id:
            aula = db.session.get(Horario, horario_id)
            if not aula: return False, 'Aula não encontrada.', 404
            if not HorarioService.can_edit_horario(aula, user): return False, 'Sem permissão para editar esta aula.', 403
        else:
            aula = Horario(status='confirmado' if is_admin else 'pendente')
            db.session.add(aula)
        
        aula.pelotao, aula.semana_id, aula.dia_semana, aula.periodo = pelotao, semana_id, dia, periodo_inicio
        aula.disciplina_id, aula.duracao, aula.observacao = disciplina_id, duracao, observacao
        aula.instrutor_id, aula.instrutor_id_2 = instrutor_id_1, instrutor_id_2

        try:
            db.session.commit()

            if not is_admin and is_new_aula:
                turma = db.session.scalar(select(Turma).where(Turma.nome == pelotao))
                if turma and turma.school_id:
                    message = f"O instrutor {user.nome_de_guerra} agendou uma nova aula de {disciplina.materia} que precisa de aprovação."
                    notification_url = url_for('horario.aprovar_horarios', _external=True)
                    NotificationService.create_notification_for_roles(turma.school_id, ['admin_escola', 'super_admin', 'programador'], message, notification_url)

            return True, 'Aula salva com sucesso!', 200
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao salvar aula: {e}")
            return False, 'Erro interno do servidor ao salvar.', 500
            
    @staticmethod
    def remove_aula(horario_id, user):
        aula = db.session.get(Horario, int(horario_id))
        if not aula: return False, 'Aula não encontrada.'
        if not HorarioService.can_edit_horario(aula, user): return False, 'Sem permissão para remover esta aula.'
        
        db.session.delete(aula)
        db.session.commit()
        return True, 'Aula removida com sucesso!'

    @staticmethod
    def get_aulas_pendentes():
        return db.session.scalars(
            select(Horario).options(
                joinedload(Horario.disciplina).joinedload(Disciplina.ciclo),
                joinedload(Horario.instrutor).joinedload(Instrutor.user),
                joinedload(Horario.semana)
            ).where(Horario.status == 'pendente').order_by(Horario.id.desc())
        ).all()
        
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
                if instrutor_user_id:
                    notif_msg_instrutor = f"Sua aula de {aula.disciplina.materia} para a turma {turma.nome} foi aprovada."
                    notif_url = url_for('horario.index', pelotao=turma.nome, semana_id=aula.semana_id, _external=True)
                    NotificationService.create_notification(instrutor_user_id, notif_msg_instrutor, notif_url)
                
                notif_msg_alunos = f"Nova aula de {aula.disciplina.materia} agendada para sua turma."
                for aluno in turma.alunos:
                    NotificationService.create_notification(aluno.user_id, notif_msg_alunos, notif_url)

        elif action == 'negar':
            db.session.delete(aula)
            message = f'Solicitação de aula de {aula.disciplina.materia} foi negada e removida.'
        else:
            return False, 'Ação inválida.'
            
        db.session.commit()
        return True, message

    @staticmethod
    def aprovar_horario_parcialmente(horario_id, periodos_para_aprovar):
        aula_pendente = db.session.get(Horario, horario_id)
        if not aula_pendente or aula_pendente.status != 'pendente':
            return False, "Aula pendente não encontrada."

        instrutor_user_id = aula_pendente.instrutor.user_id if aula_pendente.instrutor else None
        turma = db.session.scalar(select(Turma).where(Turma.nome == aula_pendente.pelotao))
        notif_url = url_for('horario.index', pelotao=aula_pendente.pelotao, semana_id=aula_pendente.semana_id, _external=True)
        
        try:
            if not periodos_para_aprovar:
                db.session.delete(aula_pendente)
                if instrutor_user_id:
                    notif_msg = f"Sua solicitação de aula de {aula_pendente.disciplina.materia} foi negada."
                    NotificationService.create_notification(instrutor_user_id, notif_msg, notif_url)
                db.session.commit()
                return True, "Aula negada com sucesso."

            todos_periodos_originais = set(range(aula_pendente.periodo, aula_pendente.periodo + aula_pendente.duracao))
            if set(periodos_para_aprovar) == todos_periodos_originais:
                aula_pendente.status = 'confirmado'
                message = "Aula aprovada com sucesso."
                if instrutor_user_id:
                    notif_msg = f"Sua aula de {aula_pendente.disciplina.materia} foi aprovada."
                    NotificationService.create_notification(instrutor_user_id, notif_msg, notif_url)
                if turma:
                    notif_msg_alunos = f"Nova aula de {aula_pendente.disciplina.materia} agendada."
                    for aluno in turma.alunos:
                        NotificationService.create_notification(aluno.user_id, notif_msg_alunos, notif_url)
            else:
                db.session.delete(aula_pendente)
                grupos_de_periodos = HorarioService._group_consecutive_periods(periodos_para_aprovar)
                
                for grupo_inicio, grupo_fim in grupos_de_periodos:
                    nova_duracao = grupo_fim - grupo_inicio + 1
                    nova_aula = Horario(
                        pelotao=aula_pendente.pelotao, dia_semana=aula_pendente.dia_semana, periodo=grupo_inicio,
                        duracao=nova_duracao, semana_id=aula_pendente.semana_id, disciplina_id=aula_pendente.disciplina_id,
                        instrutor_id=aula_pendente.instrutor_id, instrutor_id_2=aula_pendente.instrutor_id_2,
                        observacao=aula_pendente.observacao, status='confirmado'
                    )
                    db.session.add(nova_aula)

                message = "Aula parcialmente aprovada com sucesso."
                if instrutor_user_id:
                    notif_msg = f"Sua aula de {aula_pendente.disciplina.materia} foi aprovada parcialmente."
                    NotificationService.create_notification(instrutor_user_id, notif_msg, notif_url)
                if turma:
                    notif_msg_alunos = f"Nova aula de {aula_pendente.disciplina.materia} agendada (parcialmente)."
                    for aluno in turma.alunos:
                        NotificationService.create_notification(aluno.user_id, notif_msg_alunos, notif_url)
            
            db.session.commit()
            return True, message

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro na aprovação parcial: {e}")
            return False, "Ocorreu um erro ao processar a aprovação."