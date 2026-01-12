# backend/controllers/turma_controller.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from flask_login import login_required, current_user
from sqlalchemy import select, or_
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectMultipleField, SelectField
from wtforms.validators import DataRequired, Length, Optional
from wtforms.widgets import CheckboxInput, ListWidget

from ..models.database import db
from ..models.turma import Turma, TurmaStatus
from ..models.aluno import Aluno
from ..models.user import User 
from ..models.user_school import UserSchool
from ..models.turma_cargo import TurmaCargo 
from ..services.turma_service import TurmaService
from ..services.user_service import UserService 
from utils.decorators import admin_or_programmer_required, school_admin_or_programmer_required, can_view_management_pages_required

turma_bp = Blueprint('turma', __name__, url_prefix='/turma')

# USA A LISTA OFICIAL DO MODELO
CARGOS_LISTA = TurmaCargo.get_all_roles()

class TurmaForm(FlaskForm):
    nome = StringField('Nome da Turma', validators=[DataRequired(), Length(max=100)])
    ano = StringField('Ano / Edição', validators=[DataRequired(), Length(max=20)])
    status = SelectField(
        'Status da Turma',
        choices=[(s.value, s.name.replace('_', ' ').title()) for s in TurmaStatus],
        validators=[DataRequired()]
    )
    alunos_ids = SelectMultipleField('Alunos da Turma', coerce=int, validators=[Optional()],
                                     option_widget=CheckboxInput(), widget=ListWidget(prefix_label=False))
    submit = SubmitField('Salvar Turma')

class DeleteForm(FlaskForm):
    pass

@turma_bp.route('/')
@login_required
@can_view_management_pages_required
def listar_turmas():
    delete_form = DeleteForm()
    school_id = UserService.get_current_school_id()
    if not school_id:
        flash('Nenhuma escola associada.', 'warning')
        return redirect(url_for('main.dashboard'))
        
    turmas = TurmaService.get_turmas_by_school(school_id)
    if current_user.role == 'aluno' and current_user.aluno_profile and current_user.aluno_profile.turma_id:
        user_turma_id = current_user.aluno_profile.turma_id
        turmas = sorted(turmas, key=lambda t: t.id != user_turma_id)

    return render_template('listar_turmas.html', turmas=turmas, delete_form=delete_form)

@turma_bp.route('/<int:turma_id>')
@login_required
@can_view_management_pages_required
def detalhes_turma(turma_id):
    school_id = UserService.get_current_school_id()
    turma = db.session.get(Turma, turma_id)
    
    if not turma or turma.school_id != school_id:
        flash('Turma não encontrada.', 'danger')
        return redirect(url_for('turma.listar_turmas'))
    
    # Passa a lista oficial para o template
    cargos_atuais = TurmaService.get_cargos_da_turma(turma_id, CARGOS_LISTA)
    
    return render_template('detalhes_turma.html', turma=turma, cargos_lista=CARGOS_LISTA,
                           cargos_atuais=cargos_atuais)

@turma_bp.route('/<int:turma_id>/salvar-cargos', methods=['POST'])
@login_required
# Sem decorators restritivos, validamos manualmente abaixo usando o método correto do User
def salvar_cargos_turma(turma_id):
    school_id = UserService.get_current_school_id()
    if not school_id:
        flash("Sessão expirada ou escola não selecionada.", "warning")
        return redirect(url_for('main.dashboard'))

    # CORREÇÃO: Nome do método atualizado para bater com o user.py (is_sens_in_school)
    if not current_user.is_sens_in_school(school_id):
        flash("Permissão negada. Apenas Chefia de Ensino (SENS) ou Comandante podem alterar cargos.", "danger")
        return redirect(url_for('turma.detalhes_turma', turma_id=turma_id))

    turma = db.session.get(Turma, turma_id)
    if not turma or turma.school_id != school_id:
        flash('Turma não encontrada.', 'danger')
        return redirect(url_for('turma.listar_turmas'))

    success, message = TurmaService.atualizar_cargos(turma_id, request.form)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('turma.detalhes_turma', turma_id=turma_id))

@turma_bp.route('/cadastrar', methods=['GET', 'POST'])
@login_required
@school_admin_or_programmer_required
def cadastrar_turma():
    form = TurmaForm()
    school_id = UserService.get_current_school_id()
    if not school_id: return redirect(url_for('turma.listar_turmas'))

    alunos_sem_turma = db.session.scalars(select(Aluno).join(User).join(UserSchool).where(Aluno.turma_id.is_(None), UserSchool.school_id == school_id)).all()
    form.alunos_ids.choices = [(a.id, f"{a.user.nome_completo}") for a in alunos_sem_turma]

    if form.validate_on_submit():
        success, message = TurmaService.create_turma(form.data, school_id)
        if success:
            flash(message, 'success')
            return redirect(url_for('turma.listar_turmas'))
        else:
            flash(message, 'danger')
    return render_template('cadastrar_turma.html', form=form)

@turma_bp.route('/editar/<int:turma_id>', methods=['GET', 'POST'])
@login_required
@school_admin_or_programmer_required
def editar_turma(turma_id):
    school_id = UserService.get_current_school_id()
    turma = db.session.get(Turma, turma_id)
    if not turma or turma.school_id != school_id: return redirect(url_for('turma.listar_turmas'))
    
    form = TurmaForm(obj=turma)
    alunos = db.session.scalars(select(Aluno).join(User).join(UserSchool).where(UserSchool.school_id == school_id, or_(Aluno.turma_id.is_(None), Aluno.turma_id == turma_id))).all()
    form.alunos_ids.choices = [(a.id, f"{a.user.nome_completo}") for a in alunos]
    
    if form.validate_on_submit():
        success, message = TurmaService.update_turma(turma_id, form.data)
        if success:
            flash(message, 'success')
            return redirect(url_for('turma.listar_turmas'))
        else:
            flash(message, 'danger')
    if request.method == 'GET':
        form.alunos_ids.data = [a.id for a in turma.alunos]
    return render_template('editar_turma.html', form=form, turma=turma)

@turma_bp.route('/excluir/<int:turma_id>', methods=['POST'])
@login_required
@school_admin_or_programmer_required
def excluir_turma(turma_id):
    school_id = UserService.get_current_school_id()
    turma = db.session.get(Turma, turma_id)
    if not turma or turma.school_id != school_id: return redirect(url_for('turma.listar_turmas'))
    form = DeleteForm()
    if form.validate_on_submit():
        success, message = TurmaService.delete_turma(turma_id)
        flash(message, 'success' if success else 'danger')
    return redirect(url_for('turma.listar_turmas'))