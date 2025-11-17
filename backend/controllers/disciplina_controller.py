# backend/controllers/disciplina_controller.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_required, current_user
from sqlalchemy import select
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField, SelectField, SelectMultipleField
from wtforms.validators import DataRequired, Length, NumberRange, Optional
from wtforms.widgets import CheckboxInput, ListWidget


from ..models.database import db
from ..models.disciplina import Disciplina
from ..models.ciclo import Ciclo
from ..models.turma import Turma
from ..services.disciplina_service import DisciplinaService
from ..services.turma_service import TurmaService # <-- IMPORT ADICIONADO
from ..services.user_service import UserService
from utils.decorators import admin_or_programmer_required, school_admin_or_programmer_required, can_view_management_pages_required

disciplina_bp = Blueprint('disciplina', __name__, url_prefix='/disciplina')

class DisciplinaForm(FlaskForm):
    materia = StringField('Matéria', validators=[DataRequired(), Length(min=3, max=100)])
    carga_horaria_prevista = IntegerField('Carga Horária Total Prevista', validators=[DataRequired(), NumberRange(min=1)])
    carga_horaria_cumprida = IntegerField('Carga Horária Já Cumprida', validators=[Optional(), NumberRange(min=0)], default=0)
    ciclo_id = SelectField('Ciclo', coerce=int, validators=[DataRequired()])
    turma_ids = SelectMultipleField('Turmas', coerce=int, validators=[DataRequired(message="Selecione pelo menos uma turma.")],
                                      option_widget=CheckboxInput(), widget=ListWidget(prefix_label=False))
    submit = SubmitField('Salvar')

class DeleteForm(FlaskForm):
    pass

@disciplina_bp.route('/')
@login_required
@can_view_management_pages_required
def listar_disciplinas():
    school_id = UserService.get_current_school_id()
    if not school_id:
        flash('Nenhuma escola associada ou selecionada.', 'warning')
        return redirect(url_for('main.dashboard'))
        
    turma_selecionada_id = request.args.get('turma_id', type=int)
    
    # --- REFATORADO ---
    # Busca turmas e disciplinas usando os serviços
    turmas_disponiveis = TurmaService.get_turmas_by_school(school_id)
    todas_disciplinas = DisciplinaService.get_disciplinas_by_school(school_id)

    disciplinas_filtradas = []
    if turma_selecionada_id:
        # Filtra a lista em Python
        disciplinas_filtradas = [d for d in todas_disciplinas if d.turma_id == turma_selecionada_id]
    else:
        # Mostra todas as disciplinas da escola
        disciplinas_filtradas = todas_disciplinas

    # Processa apenas a lista filtrada
    disciplinas_com_progresso = []
    for d in disciplinas_filtradas:
        # d.turma já deve estar carregado (ou será pego da sessão do db)
        progresso = DisciplinaService.get_dados_progresso(d, d.turma.nome) 
        disciplinas_com_progresso.append({'disciplina': d, 'progresso': progresso})
    # --- FIM DA REFATORAÇÃO ---

    delete_form = DeleteForm()
    
    return render_template('listar_disciplinas.html', 
                           disciplinas_com_progresso=disciplinas_com_progresso, 
                           delete_form=delete_form,
                           turmas=turmas_disponiveis,
                           turma_selecionada_id=turma_selecionada_id)

@disciplina_bp.route('/adicionar', methods=['GET', 'POST'])
@login_required
@school_admin_or_programmer_required
def adicionar_disciplina():
    school_id = UserService.get_current_school_id()
    if not school_id:
        flash('Nenhuma escola associada ou selecionada.', 'danger')
        return redirect(url_for('disciplina.listar_disciplinas'))
        
    form = DisciplinaForm()
    ciclos = db.session.scalars(select(Ciclo).order_by(Ciclo.nome)).all()
    form.ciclo_id.choices = [(c.id, c.nome) for c in ciclos]
    
    # --- REFATORADO ---
    turmas = TurmaService.get_turmas_by_school(school_id)
    # ------------------
    
    form.turma_ids.choices = [(t.id, t.nome) for t in turmas]
    
    if form.validate_on_submit():
        success, message = DisciplinaService.create_disciplina(form.data, school_id)
        flash(message, 'success' if success else 'danger')
        if success:
            # Redireciona para a visão geral após o cadastro em lote
            return redirect(url_for('disciplina.listar_disciplinas'))

    return render_template('adicionar_disciplina.html', form=form)


@disciplina_bp.route('/editar/<int:disciplina_id>', methods=['GET', 'POST'])
@login_required
@school_admin_or_programmer_required
def editar_disciplina(disciplina_id):
    disciplina = db.session.get(Disciplina, disciplina_id)
    if not disciplina:
        flash('Disciplina não encontrada.', 'danger')
        return redirect(url_for('disciplina.listar_disciplinas'))

    # Usa o formulário antigo para edição individual
    class EditDisciplinaForm(FlaskForm):
        materia = StringField('Matéria', validators=[DataRequired(), Length(min=3, max=100)])
        carga_horaria_prevista = IntegerField('Carga Horária Total Prevista', validators=[DataRequired(), NumberRange(min=1)])
        carga_horaria_cumprida = IntegerField('Carga Horária Já Cumprida', validators=[Optional(), NumberRange(min=0)], default=0)
        ciclo_id = SelectField('Ciclo', coerce=int, validators=[DataRequired()])
        turma_id = SelectField('Turma', coerce=int, validators=[DataRequired(message="A turma é obrigatória.")])
        submit = SubmitField('Salvar')

    form = EditDisciplinaForm(obj=disciplina)
    ciclos = db.session.scalars(select(Ciclo).order_by(Ciclo.nome)).all()
    form.ciclo_id.choices = [(c.id, c.nome) for c in ciclos]
    form.turma_id.choices = [(disciplina.turma.id, disciplina.turma.nome)]
    
    if form.validate_on_submit():
        success, message = DisciplinaService.update_disciplina(disciplina_id, form.data)
        flash(message, 'success' if success else 'danger')
        return redirect(url_for('disciplina.listar_disciplinas', turma_id=disciplina.turma_id))

    return render_template('editar_disciplina.html', form=form, disciplina=disciplina)

@disciplina_bp.route('/excluir/<int:disciplina_id>', methods=['POST'])
@login_required
@school_admin_or_programmer_required
def excluir_disciplina(disciplina_id):
    form = DeleteForm()
    if form.validate_on_submit():
        disciplina = db.session.get(Disciplina, disciplina_id)
        turma_id = disciplina.turma_id if disciplina else None
        success, message = DisciplinaService.delete_disciplina(disciplina_id)
        flash(message, 'success' if success else 'danger')
        return redirect(url_for('disciplina.listar_disciplinas', turma_id=turma_id))

    flash('Falha na validação do token CSRF.', 'danger')
    return redirect(url_for('disciplina.listar_disciplinas'))

@disciplina_bp.route('/api/por-turma/<int:turma_id>')
@login_required
def api_disciplinas_por_turma(turma_id):
    turma = db.session.get(Turma, turma_id)
    if not turma:
        return jsonify({'error': 'Turma não encontrada'}), 404

    disciplinas = sorted(turma.disciplinas, key=lambda d: d.materia)
    return jsonify([{'id': d.id, 'materia': d.materia} for d in disciplinas])