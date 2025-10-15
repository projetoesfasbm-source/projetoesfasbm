# backend/controllers/horario_controller.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, Response
from flask_login import login_required, current_user
from sqlalchemy import select, or_
from sqlalchemy.orm import joinedload
from datetime import date
from flask_wtf import FlaskForm
from wtforms import HiddenField, SubmitField
from wtforms.validators import DataRequired
from weasyprint import HTML
from urllib.parse import quote

from ..models.database import db
from ..models.horario import Horario
from ..models.disciplina import Disciplina
from ..models.instrutor import Instrutor
from ..models.disciplina_turma import DisciplinaTurma
from ..models.semana import Semana
from ..models.turma import Turma
from ..models.ciclo import Ciclo
from ..models.user import User
from ..services.site_config_service import SiteConfigService
from utils.decorators import admin_or_programmer_required, can_schedule_classes_required
from ..services.horario_service import HorarioService
from ..services.user_service import UserService

horario_bp = Blueprint('horario', __name__, url_prefix='/horario')

class AprovarHorarioForm(FlaskForm):
    horario_id = HiddenField('Horário ID', validators=[DataRequired()])
    action = HiddenField('Ação', validators=[DataRequired()])
    submit = SubmitField('Enviar')

def _get_horario_context_data():
    """
    Busca e prepara os dados de horários e intervalos usando o método
    robusto get_config para cada item.
    """
    tempos = []
    for i in range(1, 16):
        key = f"horario_periodo_{i:02d}"
        periodo_str = f"{i}º"
        time_str = SiteConfigService.get_config(key, 'N/D')
        tempos.append((periodo_str, time_str))
    
    intervalos = {
        'intervalo_1': SiteConfigService.get_config('horario_intervalo_manha', 'N/D'),
        'almoco': SiteConfigService.get_config('horario_intervalo_almoco', 'N/D'),
        'intervalo_2': SiteConfigService.get_config('horario_intervalo_tarde', 'N/D'),
    }
    return tempos, intervalos


@horario_bp.route('/')
@login_required
def index():
    if current_user.role == 'aluno':
        if not current_user.aluno_profile or not current_user.aluno_profile.turma:
            flash("Você não está matriculado em nenhuma turma. Contate a administração.", 'warning')
            return redirect(url_for('main.dashboard'))
        turma_do_aluno = current_user.aluno_profile.turma
        school_id = turma_do_aluno.school_id
        turma_selecionada_nome = turma_do_aluno.nome
        todas_as_turmas = [turma_do_aluno]
    else:
        school_id = UserService.get_current_school_id()
        if not school_id:
            flash("Nenhuma escola associada ou selecionada.", "warning")
            return redirect(url_for('main.dashboard'))
        
        todas_as_turmas = db.session.scalars(select(Turma).where(Turma.school_id == school_id).order_by(Turma.nome)).all()
        turma_selecionada_nome = request.args.get('pelotao', session.get('ultima_turma_visualizada'))
        
        if not turma_selecionada_nome and todas_as_turmas:
            turma_selecionada_nome = todas_as_turmas[0].nome
        elif turma_selecionada_nome and turma_selecionada_nome not in [t.nome for t in todas_as_turmas]:
             flash("Turma selecionada inválida.", "danger")
             turma_selecionada_nome = todas_as_turmas[0].nome if todas_as_turmas else None

    ciclo_selecionado_id = request.args.get('ciclo', session.get('ultimo_ciclo_horario', 1), type=int)
    session['ultimo_ciclo_horario'] = ciclo_selecionado_id
    
    ciclos = db.session.scalars(select(Ciclo).order_by(Ciclo.id)).all()
    
    todas_as_semanas = []
    if school_id:
        todas_as_semanas = db.session.scalars(select(Semana).where(Semana.ciclo_id == ciclo_selecionado_id).order_by(Semana.data_inicio.desc())).all()
    
    semana_id = request.args.get('semana_id')
    semana_selecionada = HorarioService.get_semana_selecionada(semana_id, ciclo_selecionado_id)
    
    horario_matrix = None
    datas_semana = {}
    if turma_selecionada_nome and semana_selecionada:
        session['ultima_turma_visualizada'] = turma_selecionada_nome
        horario_matrix = HorarioService.construir_matriz_horario(turma_selecionada_nome, semana_selecionada.id, current_user)
        datas_semana = HorarioService.get_datas_da_semana(semana_selecionada)

    can_schedule_in_this_turma = False
    instrutor_turmas_vinculadas = [] 

    if current_user.role in ['programador', 'admin_escola', 'super_admin']:
        can_schedule_in_this_turma = True
    elif current_user.role == 'instrutor' and current_user.instrutor_profile:
        instrutor_id = current_user.instrutor_profile.id
        pelotao_names = db.session.scalars(select(DisciplinaTurma.pelotao).where(or_(DisciplinaTurma.instrutor_id_1 == instrutor_id, DisciplinaTurma.instrutor_id_2 == instrutor_id)).distinct()).all()
        if pelotao_names:
            instrutor_turmas_vinculadas = db.session.scalars(select(Turma).where(Turma.nome.in_(pelotao_names)).order_by(Turma.nome)).all()
        if turma_selecionada_nome in pelotao_names:
            can_schedule_in_this_turma = True

    tempos, intervalos = _get_horario_context_data()

    return render_template('quadro_horario.html',
                           horario_matrix=horario_matrix,
                           pelotao_selecionado=turma_selecionada_nome,
                           semana_selecionada=semana_selecionada,
                           todas_as_turmas=todas_as_turmas,
                           todas_as_semanas=todas_as_semanas,
                           ciclos=ciclos,
                           ciclo_selecionado=ciclo_selecionado_id,
                           datas_semana=datas_semana,
                           can_schedule_in_this_turma=can_schedule_in_this_turma,
                           instrutor_turmas_vinculadas=instrutor_turmas_vinculadas,
                           tempos=tempos,
                           intervalos=intervalos)

@horario_bp.route('/exportar-pdf')
@login_required
@admin_or_programmer_required
def exportar_pdf():
    pelotao = request.args.get('pelotao')
    semana_id = request.args.get('semana_id', type=int)
    if not pelotao or not semana_id:
        flash('Parâmetros inválidos para gerar o PDF.', 'danger')
        return redirect(url_for('horario.index'))
    semana = db.session.get(Semana, semana_id)
    if not semana:
        flash('Semana não encontrada.', 'danger')
        return redirect(url_for('horario.index'))
    horario_matrix = HorarioService.construir_matriz_horario(pelotao, semana_id, current_user)
    datas_semana = HorarioService.get_datas_da_semana(semana)
    rendered_html = render_template('horario_pdf.html', pelotao_selecionado=pelotao, semana_selecionada=semana, horario_matrix=horario_matrix, datas_semana=datas_semana)
    try:
        pdf_content = HTML(string=rendered_html, base_url=request.url_root).write_pdf()
        filename_utf8 = f'horario_{pelotao}_{semana.nome}.pdf'.replace(' ', '_')
        filename_ascii = 'quadro_horario.pdf'
        return Response(pdf_content, mimetype='application/pdf', headers={'Content-Disposition': f'attachment; filename="{filename_ascii}"; filename*=UTF-8\'\'{quote(filename_utf8)}'})
    except Exception as e:
        flash(f'Erro ao gerar PDF: {e}', 'danger')
        return redirect(url_for('horario.index', pelotao=pelotao, semana_id=semana_id))

@horario_bp.route('/editar/<pelotao>/<int:semana_id>/<int:ciclo_id>')
@login_required
@can_schedule_classes_required
def editar_horario_grid(pelotao, semana_id, ciclo_id):
    semana = db.session.get(Semana, semana_id)
    if not semana:
        flash("Semana não encontrada.", "danger")
        return redirect(url_for('horario.index'))
    context_data = HorarioService.get_edit_grid_context(pelotao, semana_id, ciclo_id, current_user)
    if not context_data.get('success'):
        flash(context_data.get('message', 'Erro ao carregar dados.'), 'danger')
        return redirect(url_for('horario.index'))
    tempos, intervalos = _get_horario_context_data()
    context_data['tempos'] = tempos
    context_data['intervalos'] = intervalos
    return render_template('editar_quadro_horario.html', **context_data)

@horario_bp.route('/get-aula/<int:horario_id>')
@login_required
def get_aula_details(horario_id):
    aula_details = HorarioService.get_aula_details(horario_id, current_user)
    if not aula_details:
        return jsonify({'success': False, 'message': 'Aula não encontrada.'}), 404
    return jsonify({'success': True, **aula_details})

@horario_bp.route('/api/instrutores-vinculados/<pelotao>/<int:disciplina_id>')
@login_required
def get_instrutores_vinculados(pelotao, disciplina_id):
    vinculo = db.session.scalar(select(DisciplinaTurma).options(joinedload(DisciplinaTurma.instrutor_1).joinedload(Instrutor.user), joinedload(DisciplinaTurma.instrutor_2).joinedload(Instrutor.user)).where(DisciplinaTurma.pelotao == pelotao, DisciplinaTurma.disciplina_id == disciplina_id))
    if not vinculo: return jsonify([])
    opcoes = []
    if vinculo.instrutor_1:
        posto = vinculo.instrutor_1.user.posto_graduacao or ''
        nome_guerra = vinculo.instrutor_1.user.nome_de_guerra or vinculo.instrutor_1.user.username
        opcoes.append({'id': vinculo.instrutor_1.id, 'nome': f"{posto} {nome_guerra}"})
    if vinculo.instrutor_2:
        posto = vinculo.instrutor_2.user.posto_graduacao or ''
        nome_guerra = vinculo.instrutor_2.user.nome_de_guerra or vinculo.instrutor_2.user.username
        opcoes.append({'id': vinculo.instrutor_2.id, 'nome': f"{posto} {nome_guerra}"})
    if vinculo.instrutor_1 and vinculo.instrutor_2:
        id_combinado = f"{vinculo.instrutor_1.id}-{vinculo.instrutor_2.id}"
        posto1, nome1 = (vinculo.instrutor_1.user.posto_graduacao or ''), (vinculo.instrutor_1.user.nome_de_guerra or vinculo.instrutor_1.user.username)
        posto2, nome2 = (vinculo.instrutor_2.user.posto_graduacao or ''), (vinculo.instrutor_2.user.nome_de_guerra or vinculo.instrutor_2.user.username)
        nome_combinado = f"{posto1} {nome1} e {posto2} {nome2}"
        opcoes.append({'id': id_combinado, 'nome': nome_combinado})
    return jsonify(opcoes)

@horario_bp.route('/salvar-aula', methods=['POST'])
@login_required
def salvar_aula():
    data = request.json
    success, message, status_code = HorarioService.save_aula(data, current_user)
    return jsonify({'success': success, 'message': message}), status_code

@horario_bp.route('/remover-aula', methods=['POST'])
@login_required
def remover_aula():
    data = request.json
    horario_id = data.get('horario_id')
    success, message = HorarioService.remove_aula(horario_id, current_user)
    if success: return jsonify({'success': True, 'message': message})
    else: return jsonify({'success': False, 'message': message}), 403

@horario_bp.route('/aprovar', methods=['GET', 'POST'])
@login_required
@admin_or_programmer_required
def aprovar_horarios():
    form = AprovarHorarioForm()
    if form.validate_on_submit():
        horario_id = form.horario_id.data
        action = form.action.data
        success, message = HorarioService.aprovar_horario(horario_id, action)
        flash(message, 'success' if success else 'danger')
        return redirect(url_for('horario.aprovar_horarios'))
    aulas_pendentes = HorarioService.get_aulas_pendentes()
    return render_template('aprovar_horarios.html', aulas_pendentes=aulas_pendentes, form=form)