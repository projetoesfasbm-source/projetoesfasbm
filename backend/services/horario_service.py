# backend/services/horario_service.py

from flask import current_app, url_for
from flask_login import current_user
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import joinedload
from datetime import date, timedelta
from collections import defaultdict
import uuid
import json

from ..models.database import db
from ..models.horario import Horario
from ..models.disciplina import Disciplina
from ..models.instrutor import Instrutor
from ..models.disciplina_turma import DisciplinaTurma
from ..models.semana import Semana
from ..models.turma import Turma
from ..models.user import User
from .notification_service import NotificationService
from .instrutor_service import InstrutorService
from .site_config_service import SiteConfigService

class HorarioService:

    @staticmethod
    def can_edit_horario(horario, user):
        """Regras de edição de um horário por perfil."""
        if not horario or not user:
            return False
        if user.role in ['super_admin', 'programador', 'admin_escola']:
            return True
        if user.role == 'instrutor' and user.instrutor_profile:
            instrutor_id = user.instrutor_profile.id
            return (
                horario.instrutor_id == instrutor_id or
                horario.instrutor_id_2 == instrutor_id
            )
        return False

    @staticmethod
    def construir_matriz_horario(pelotao, semana_id, user):
        """Monta a grade 15x7 com placeholders e aulas."""
        a_disposicao = {
            'materia': 'A disposição do C Al /S Ens',
            'instrutor': None,
            'duracao': 1,
            'is_disposicao': True,
            'id': None,
            'status': 'confirmado'
        }
        horario_matrix = [[dict(a_disposicao) for _ in range(7)] for _ in range(15)]
        dias = ['segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado', 'domingo']

        aulas_query = (
            select(Horario)
            .options(
                joinedload(Horario.disciplina),
                joinedload(Horario.instrutor).joinedload(Instrutor.user),
                joinedload(Horario.instrutor_2).joinedload(Instrutor.user),
            )
            .where(Horario.pelotao == pelotao, Horario.semana_id == semana_id)
        )
        all_aulas = db.session.scalars(aulas_query).all()

        for aula in all_aulas:
            try:
                dia_idx = dias.index(aula.dia_semana)
                periodo_idx = aula.periodo - 1

                can_see_pending_details = HorarioService.can_edit_horario(aula, user)
                show_details = aula.status == 'confirmado' or can_see_pending_details

                instrutores_display_list = []
                if aula.instrutor and aula.instrutor.user:
                    # Formata nome com Posto/Graduação
                    posto = aula.instrutor.user.posto_graduacao or ''
                    nome = aula.instrutor.user.nome_de_guerra or aula.instrutor.user.username
                    nome_completo = f"{posto} {nome}".strip()
                    instrutores_display_list.append(nome_completo)
                
                if aula.instrutor_2 and aula.instrutor_2.user:
                    # Formata nome com Posto/Graduação
                    posto = aula.instrutor_2.user.posto_graduacao or ''
                    nome = aula.instrutor_2.user.nome_de_guerra or aula.instrutor_2.user.username
                    nome_completo = f"{posto} {nome}".strip()
                    instrutores_display_list.append(nome_completo)
                
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
                    'is_continuation': False,
                    'group_id': aula.group_id,
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
            select(Semana)
            .where(Semana.ciclo_id == ciclo_id)
            .order_by(Semana.data_inicio.desc())
        ).first()

    @staticmethod
    def get_datas_da_semana(semana):
        if not semana:
            return {}
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
            return (
                db.session.scalar(
                    select(func.sum(Horario.duracao)).where(
                        Horario.disciplina_id == disciplina_id,
                        Horario.pelotao == pelotao_nome,
                    )
                )
                or 0
            )

        turma_obj = db.session.scalar(select(Turma).where(Turma.nome == pelotao))
        if not turma_obj:
            return {'success': False, 'message': 'Turma não encontrada.'}

        disciplinas_disponiveis = []
        if is_admin:
            disciplinas_da_turma = db.session.scalars(
                select(Disciplina)
                .where(Disciplina.turma_id == turma_obj.id)
                .order_by(Disciplina.materia)
            ).all()
            for d in disciplinas_da_turma:
                horas_restantes = d.carga_horaria_prevista - get_horas_agendadas(d.id, pelotao)
                disciplinas_disponiveis.append(
                    {"id": d.id, "nome": d.materia, "restantes": horas_restantes}
                )
        else:
            instrutor_id = user.instrutor_profile.id if user.instrutor_profile else 0
            disciplinas_do_instrutor = db.session.scalars(
                select(Disciplina)
                .join(DisciplinaTurma, Disciplina.id == DisciplinaTurma.disciplina_id)
                .where(
                    Disciplina.turma_id == turma_obj.id,
                    or_(
                        DisciplinaTurma.instrutor_id_1 == instrutor_id,
                        DisciplinaTurma.instrutor_id_2 == instrutor_id,
                    ),
                )
                .order_by(Disciplina.materia)
            ).all()
            for d in disciplinas_do_instrutor:
                horas_restantes = d.carga_horaria_prevista - get_horas_agendadas(d.id, pelotao)
                disciplinas_disponiveis.append(
                    {"id": d.id, "nome": d.materia, "restantes": horas_restantes}
                )

        instrutores_paginados = InstrutorService.get_all_instrutores(user=user)
        todos_instrutores = []
        for i in instrutores_paginados.items:
            posto = i.user.posto_graduacao or ''
            nome = i.user.nome_de_guerra or i.user.username
            todos_instrutores.append({"id": i.id, "nome": f"{posto} {nome}".strip()})

        return {
            'success': True,
            'horario_matrix': horario_matrix,
            'pelotao_selecionado': pelotao,
            'semana_selecionada': semana,
            'disciplinas_disponiveis': disciplinas_disponiveis,
            'todos_instrutores': todos_instrutores,
            'is_admin': is_admin,
            'instrutor_logado_id': user.instrutor_profile.id if user.instrutor_profile else None,
            'datas_semana': HorarioService.get_datas_da_semana(semana),
        }

    @staticmethod
    def get_aula_details(horario_id, user):
        aula = db.session.get(Horario, horario_id)
        if not aula or not HorarioService.can_edit_horario(aula, user):
            return None

        # Lista exata de períodos
        periodos_ocupados = []
        if aula.group_id:
            blocos = db.session.scalars(
                select(Horario).where(Horario.group_id == aula.group_id)
            ).all()
        else:
            blocos = [aula]

        for bloco in blocos:
            for i in range(bloco.duracao):
                periodos_ocupados.append(bloco.periodo + i)
        periodos_ocupados.sort()

        instrutor_value = str(aula.instrutor_id)
        if aula.instrutor_id_2:
            instrutor_value = f"{aula.instrutor_id}-{aula.instrutor_id_2}"

        instrutor_nome_formatado = ''
        if aula.instrutor and aula.instrutor.user:
            posto = aula.instrutor.user.posto_graduacao or ''
            nome = aula.instrutor.user.nome_de_guerra or aula.instrutor.user.username
            instrutor_nome_formatado = f"{posto} {nome}".strip()

        return {
            'disciplina_id': aula.disciplina_id,
            'instrutor_value': instrutor_value,
            'periodos': periodos_ocupados,
            'observacao': aula.observacao,
            'materia': aula.disciplina.materia,
            'instrutor_nome': instrutor_nome_formatado,
            'periodo': periodos_ocupados[0] if periodos_ocupados else aula.periodo,
            'duracao': len(periodos_ocupados)
        }

    @staticmethod
    def _consolidar_aulas_adjacentes(pelotao, semana_id, dia_semana):
        break_points = {3, 6, 9}

        aulas = db.session.scalars(
            select(Horario)
            .where(
                Horario.pelotao == pelotao,
                Horario.semana_id == semana_id,
                Horario.dia_semana == dia_semana
            )
            .order_by(Horario.periodo)
        ).all()

        if not aulas:
            return

        i = 0
        while i < len(aulas) - 1:
            atual = aulas[i]
            proximo = aulas[i+1]

            fim_atual = atual.periodo + atual.duracao - 1
            inicio_proximo = proximo.periodo
            sao_adjacentes = (fim_atual + 1) == inicio_proximo
            respeita_intervalo = fim_atual not in break_points

            mesmos_atributos = (
                atual.disciplina_id == proximo.disciplina_id and
                atual.instrutor_id == proximo.instrutor_id and
                atual.instrutor_id_2 == proximo.instrutor_id_2 and
                atual.status == proximo.status and
                (atual.observacao or '') == (proximo.observacao or '')
            )

            if sao_adjacentes and respeita_intervalo and mesmos_atributos:
                atual.duracao += proximo.duracao
                if not atual.group_id:
                    atual.group_id = proximo.group_id or str(uuid.uuid4())
                db.session.delete(proximo)
                aulas.pop(i+1)
            else:
                i += 1

    @staticmethod
    def save_aula(data, user):
        try:
            is_admin = user.role in ['super_admin', 'programador', 'admin_escola']

            pelotao = data['pelotao']
            semana_id = int(data.get('semana_id', 0))
            disciplina_id = int(data.get('disciplina_id', 0))
            dia = data['dia']
            periodo_inicio = int(data['periodo'])
            duracao = int(data.get('duracao', 1))
            periodo_fim = periodo_inicio + duracao - 1
            observacao = data.get('observacao', '').strip() or None
            
            horario_id_raw = data.get('horario_id')
            horario_id = int(horario_id_raw) if horario_id_raw else None

            # Recupera a Semana para validações
            semana = db.session.get(Semana, semana_id)
            if not semana:
                return False, "Semana não encontrada.", 404

            # --- BLOCO DE VALIDAÇÕES DE INTEGRIDADE (NOVO) ---
            # Aplica regras estritas para não-administradores
            if not is_admin:
                
                # 1. Validação de Dias da Semana (Sábado/Domingo)
                # Verifica se o dia está habilitado na configuração da semana
                if dia == 'sabado' and not semana.mostrar_sabado:
                    return False, "⚠️ AGENDAMENTO BLOQUEADO: O Sábado não está habilitado nesta semana.", 403
                
                if dia == 'domingo' and not semana.mostrar_domingo:
                    return False, "⚠️ AGENDAMENTO BLOQUEADO: O Domingo não está habilitado nesta semana.", 403

                # 2. Validação de Períodos Especiais (13, 14, 15 e Limites de Fim de Semana)
                # Verifica cada período que a aula vai ocupar
                for p in range(periodo_inicio, periodo_fim + 1):
                    
                    # Períodos Extras
                    if p == 13 and not semana.mostrar_periodo_13:
                        return False, "⚠️ AGENDAMENTO BLOQUEADO: O 13º tempo não está habilitado.", 403
                    if p == 14 and not semana.mostrar_periodo_14:
                        return False, "⚠️ AGENDAMENTO BLOQUEADO: O 14º tempo não está habilitado.", 403
                    if p == 15 and not semana.mostrar_periodo_15:
                        return False, "⚠️ AGENDAMENTO BLOQUEADO: O 15º tempo não está habilitado.", 403
                    
                    # Limites de quantidade de tempos no Fim de Semana (se configurado)
                    if dia == 'sabado' and semana.periodos_sabado > 0 and p > semana.periodos_sabado:
                        return False, f"⚠️ AGENDAMENTO BLOQUEADO: Sábado nesta semana vai apenas até o {semana.periodos_sabado}º tempo.", 403
                    
                    if dia == 'domingo' and semana.periodos_domingo > 0 and p > semana.periodos_domingo:
                        return False, f"⚠️ AGENDAMENTO BLOQUEADO: Domingo nesta semana vai apenas até o {semana.periodos_domingo}º tempo.", 403

            # --- VALIDAÇÃO DE CARGA HORÁRIA (Mantida) ---
            disciplina = db.session.get(Disciplina, disciplina_id)
            if disciplina and not is_admin: 
                total_agendado = db.session.scalar(
                    select(func.sum(Horario.duracao))
                    .where(Horario.disciplina_id == disciplina_id, Horario.pelotao == pelotao)
                ) or 0
                
                if horario_id:
                     aula_atual_editando = db.session.get(Horario, horario_id)
                     if aula_atual_editando:
                         if aula_atual_editando.group_id:
                             total_grupo = db.session.scalar(
                                 select(func.sum(Horario.duracao))
                                 .where(Horario.group_id == aula_atual_editando.group_id)
                             ) or 0
                             total_agendado -= total_grupo
                         else:
                             total_agendado -= aula_atual_editando.duracao

                if (total_agendado + duracao) > disciplina.carga_horaria_prevista:
                    restante = disciplina.carga_horaria_prevista - total_agendado
                    # Evita números negativos na mensagem
                    if restante < 0: restante = 0
                    return False, f"⚠️ LIMITE EXCEDIDO: Faltam apenas {restante}h. Você tentou agendar {duracao}h.", 400
            # ---------------------------------------------

            # --- LÓGICA DE BLOQUEIO POR PRIORIDADE ---
            if semana and getattr(semana, 'priority_active', False) and not is_admin:
                allowed_names = []
                raw_priority = getattr(semana, 'priority_disciplines', '[]') or '[]'
                try:
                    allowed_names = json.loads(raw_priority)
                    if not isinstance(allowed_names, list): allowed_names = []
                except:
                    allowed_names = []
                
                nome_disciplina_atual = disciplina.materia if disciplina else ""

                if not allowed_names or nome_disciplina_atual not in allowed_names:
                    return False, "⚠️ AGENDAMENTO BLOQUEADO: Apenas as disciplinas prioritárias podem ser agendadas nesta semana.", 403
            # -------------------------------------------------------------

            # instrutor(es)
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

            # Busca automática do segundo instrutor (vínculo)
            if not instrutor_id_2:
                vinculo_dt = db.session.scalar(
                    select(DisciplinaTurma).where(
                        DisciplinaTurma.disciplina_id == disciplina_id,
                        DisciplinaTurma.pelotao == pelotao
                    )
                )
                
                if vinculo_dt:
                    if vinculo_dt.instrutor_id_1 == instrutor_id_1 and vinculo_dt.instrutor_id_2:
                        instrutor_id_2 = vinculo_dt.instrutor_id_2
                    elif vinculo_dt.instrutor_id_2 == instrutor_id_1 and vinculo_dt.instrutor_id_1:
                        instrutor_id_2 = vinculo_dt.instrutor_id_1

            # edição
            if horario_id:
                aula_original = db.session.get(Horario, horario_id)
                if not aula_original or not HorarioService.can_edit_horario(aula_original, user):
                    return False, 'Aula não encontrada ou sem permissão para editar.', 404
                if aula_original.group_id:
                    db.session.query(Horario).filter(Horario.group_id == aula_original.group_id).delete()
                else:
                    db.session.delete(aula_original)
                db.session.flush()

            break_points = {3, 6, 9}
            group_id = str(uuid.uuid4()) if duracao > 1 else None
            periodos_restantes = list(range(periodo_inicio, periodo_fim + 1))

            while periodos_restantes:
                periodo_bloco_inicio = periodos_restantes[0]
                periodo_bloco_fim = periodo_bloco_inicio
                for i in range(1, len(periodos_restantes)):
                    if (
                        periodos_restantes[i] == periodo_bloco_fim + 1
                        and periodo_bloco_fim not in break_points
                    ):
                        periodo_bloco_fim = periodos_restantes[i]
                    else:
                        break

                duracao_bloco = (periodo_bloco_fim - periodo_bloco_inicio) + 1

                # conflito
                query_conflito = select(Horario).where(
                    Horario.pelotao == pelotao,
                    Horario.semana_id == semana_id,
                    Horario.dia_semana == dia,
                    Horario.periodo <= periodo_bloco_fim,
                    (Horario.periodo + Horario.duracao - 1) >= periodo_bloco_inicio,
                )
                if db.session.execute(query_conflito).scalars().first():
                    return False, f'Conflito de horário no período {periodo_bloco_inicio}.', 409

                nova_aula_bloco = Horario(
                    pelotao=pelotao,
                    semana_id=semana_id,
                    dia_semana=dia,
                    periodo=periodo_bloco_inicio,
                    duracao=duracao_bloco,
                    disciplina_id=disciplina_id,
                    observacao=observacao,
                    instrutor_id=instrutor_id_1,
                    instrutor_id_2=instrutor_id_2,
                    status='confirmado' if is_admin else 'pendente',
                    group_id=group_id,
                )
                db.session.add(nova_aula_bloco)

                periodos_restantes = periodos_restantes[duracao_bloco:]

            # notificação
            if not is_admin:
                disciplina = db.session.get(Disciplina, disciplina_id)
                turma = db.session.scalar(select(Turma).where(Turma.nome == pelotao))
                
                if turma and turma.school_id:
                    message = (
                        f"O instrutor {user.nome_de_guerra} agendou uma nova aula de "
                        f"{disciplina.materia} que precisa de aprovação."
                    )
                    notification_url = url_for('horario.aprovar_horarios', _external=True)
                    NotificationService.create_notification_for_roles(
                        turma.school_id,
                        ['admin_escola', 'super_admin', 'programador'],
                        message,
                        notification_url,
                    )

            db.session.flush() 
            HorarioService._consolidar_aulas_adjacentes(pelotao, semana_id, dia)
            db.session.commit()
            return True, 'Aula salva com sucesso!', 200
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao salvar aula: {e}")
            return False, 'Erro interno do servidor ao salvar.', 500

    @staticmethod
    def remove_aula(horario_id, user):
        aula = db.session.get(Horario, int(horario_id))
        if not aula or not HorarioService.can_edit_horario(aula, user):
            return False, 'Aula não encontrada ou sem permissão.'
        if aula.group_id:
            db.session.query(Horario).filter(Horario.group_id == aula.group_id).delete()
        else:
            db.session.delete(aula)

        db.session.commit()
        return True, 'Aula removida com sucesso!'

    @staticmethod
    def get_aulas_pendentes():
        return db.session.scalars(
            select(Horario)
            .options(
                joinedload(Horario.disciplina).joinedload(Disciplina.ciclo),
                joinedload(Horario.instrutor).joinedload(Instrutor.user),
                joinedload(Horario.semana),
            )
            .where(Horario.status == 'pendente')
            .order_by(Horario.id.desc())
        ).all()

    @staticmethod
    def get_aulas_pendentes_agrupadas():
        aulas_pendentes_flat = HorarioService.get_aulas_pendentes()
        grouped_aulas = defaultdict(list)
        single_aulas = []

        for aula in aulas_pendentes_flat:
            if aula.group_id:
                grouped_aulas[aula.group_id].append(aula)
            else:
                single_aulas.append(aula)

        aulas_para_template = []

        for aula in single_aulas:
            aulas_para_template.append({
                'aula': aula,
                'periodo_str': f"{aula.periodo}º ({aula.duracao}h)",
                'id_para_acao': aula.id,
            })

        for group_id, aulas_no_grupo in grouped_aulas.items():
            if not aulas_no_grupo:
                continue

            aulas_no_grupo.sort(key=lambda a: a.periodo)
            primeira_aula = aulas_no_grupo[0]

            total_duracao = sum(a.duracao for a in aulas_no_grupo)
            periodo_min = min(a.periodo for a in aulas_no_grupo)
            periodo_max = max(a.periodo + a.duracao - 1 for a in aulas_no_grupo)

            if periodo_min != periodo_max:
                periodo_str = f"{periodo_min}º ao {periodo_max}º ({total_duracao}h)"
            else:
                periodo_str = f"{periodo_min}º ({total_duracao}h)"

            aulas_para_template.append({
                'aula': primeira_aula,
                'periodo_str': periodo_str,
                'id_para_acao': primeira_aula.id,
            })

        aulas_para_template.sort(key=lambda x: x['aula'].id, reverse=True)
        return aulas_para_template

    @staticmethod
    def aprovar_horario(horario_id, action):
        aula_representativa = db.session.get(Horario, int(horario_id))
        if not aula_representativa:
            return False, 'Aula não encontrada.'
        if aula_representativa.group_id:
            aulas_para_alterar = db.session.scalars(
                select(Horario).where(Horario.group_id == aula_representativa.group_id)
            ).all()
        else:
            aulas_para_alterar = [aula_representativa]

        if not aulas_para_alterar:
            return False, 'Nenhuma aula encontrada para a ação.'

        instrutor_user_id = aulas_para_alterar[0].instrutor.user_id if aulas_para_alterar[0].instrutor else None
        disciplina_materia = aulas_para_alterar[0].disciplina.materia
        turma_nome = aulas_para_alterar[0].pelotao

        if action == 'aprovar':
            for aula in aulas_para_alterar:
                aula.status = 'confirmado'
            message = f'Agendamento de {disciplina_materia} aprovado.'
            turma = db.session.scalar(select(Turma).where(Turma.nome == turma_nome))
            if turma:
                notif_url = url_for(
                    'horario.index',
                    pelotao=turma.nome,
                    semana_id=aulas_para_alterar[0].semana_id,
                    _external=True
                )
                if instrutor_user_id:
                    NotificationService.create_notification(
                        instrutor_user_id,
                        f"Seu agendamento de {disciplina_materia} para a turma {turma.nome} foi aprovado.",
                        notif_url
                    )
                for aluno in turma.alunos:
                    NotificationService.create_notification(
                        aluno.user_id,
                        f"Nova aula de {disciplina_materia} agendada para sua turma.",
                        notif_url
                    )

        elif action == 'negar':
            for aula in aulas_para_alterar:
                db.session.delete(aula)
            message = f'Solicitação de aula de {disciplina_materia} foi negada e removida.'
        else:
            return False, 'Ação inválida.'
        db.session.commit()
        return True, message

    @staticmethod
    def _group_consecutive_periods(periods):
        if not periods:
            return []
        sorted_periods = sorted(periods)
        groups, current_group_start = [], sorted_periods[0]
        for i in range(1, len(sorted_periods)):
            if sorted_periods[i] != sorted_periods[i - 1] + 1:
                groups.append((current_group_start, sorted_periods[i - 1]))
                current_group_start = sorted_periods[i]
        groups.append((current_group_start, sorted_periods[-1]))
        return groups

    @staticmethod
    def aprovar_horario_parcialmente(horario_id, periodos_para_aprovar):
        aula_pendente = db.session.get(Horario, horario_id)
        if not aula_pendente or aula_pendente.status != 'pendente':
            return False, "Aula pendente não encontrada."

        instrutor_user_id = aula_pendente.instrutor.user_id if aula_pendente.instrutor else None
        turma = db.session.scalar(select(Turma).where(Turma.nome == aula_pendente.pelotao))
        notif_url = url_for(
            'horario.index',
            pelotao=aula_pendente.pelotao,
            semana_id=aula_pendente.semana_id,
            _external=True
        )

        try:
            if aula_pendente.group_id:
                db.session.query(Horario).filter(Horario.group_id == aula_pendente.group_id).delete()
            else:
                db.session.delete(aula_pendente)
            
            db.session.flush()
            
            if not periodos_para_aprovar:
                message = "Aula negada com sucesso."
                if instrutor_user_id:
                    NotificationService.create_notification(
                        instrutor_user_id,
                        f"Sua solicitação de aula de {aula_pendente.disciplina.materia} foi negada.",
                        notif_url
                    )
                db.session.commit()
                return True, message

            message = "Aula aprovada com sucesso."
            for grupo_inicio, grupo_fim in HorarioService._group_consecutive_periods(periodos_para_aprovar):
                nova_aula = Horario(
                    pelotao=aula_pendente.pelotao,
                    dia_semana=aula_pendente.dia_semana,
                    periodo=grupo_inicio,
                    duracao=(grupo_fim - grupo_inicio + 1),
                    semana_id=aula_pendente.semana_id,
                    disciplina_id=aula_pendente.disciplina_id,
                    instrutor_id=aula_pendente.instrutor_id,
                    instrutor_id_2=aula_pendente.instrutor_id_2,
                    observacao=aula_pendente.observacao,
                    status='confirmado',
                )
                db.session.add(nova_aula)

            total_orig = sum(h.duracao for h in db.session.scalars(select(Horario).where(Horario.group_id == aula_pendente.group_id)).all()) if aula_pendente.group_id else aula_pendente.duracao
            if len(periodos_para_aprovar) != total_orig:
                message = "Aula parcialmente aprovada com sucesso."

            notif_msg_instrutor = f"Sua aula de {aula_pendente.disciplina.materia} foi aprovada."
            notif_msg_alunos = f"Nova aula de {aula_pendente.disciplina.materia} agendada."
            
            if instrutor_user_id:
                NotificationService.create_notification(
                    instrutor_user_id, notif_msg_instrutor, notif_url
                )
            if turma:
                for aluno in turma.alunos:
                    NotificationService.create_notification(aluno.user_id, notif_msg_alunos, notif_url)

            db.session.commit()
            return True, message
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro na aprovação parcial: {e}")
            return False, "Ocorreu um erro ao processar a aprovação."