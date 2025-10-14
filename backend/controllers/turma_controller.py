# backend/controllers/turma_controller.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import select, or_
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField, SelectMultipleField
from wtforms.validators import DataRequired, Length, NumberRange, Optional
from wtforms.widgets import CheckboxInput, ListWidget

from ..models.database import db
from ..models.turma import Turma
from ..models.aluno import Aluno
from ..models.user import User 
from ..models.user_school import UserSchool
from ..services.turma_service import TurmaService
from ..services.user_service import UserService 
from utils.decorators import admin_or_programmer_required, school_admin_or_programmer_required, can_view_management_pages_required

turma_bp = Blueprint('turma', __name__, url_prefix='/turma')

CARGOS_LISTA = [
    "Auxiliar do Pelotão", "Chefe de Turma", "C1", "C2", "C3", "C4", "C5"
]

class TurmaForm(FlaskForm):
    nome = StringField('Nome da Turma', validators=[DataRequired(), Length(max=100)])
    ano = IntegerField('Ano da Turma', validators=[DataRequired(), NumberRange(min=2000, max=2100)])
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
    turmas = db.session.scalars(select(Turma).order_by(Turma.nome)).all()

    if current_user.role == 'aluno' and current_user.aluno_profile and current_user.aluno_profile.turma_id:
        user_turma_id = current_user.aluno_profile.turma_id
        turmas = sorted(turmas, key=lambda t: t.id != user_turma_id)

    return render_template('listar_turmas.html', turmas=turmas, delete_form=delete_form)

@turma_bp.route('/<int:turma_id>')
@login_required
@can_view_management_pages_required
def detalhes_turma(turma_id):
    turma = db.session.get(Turma, turma_id)
    if not turma:
        flash('Turma não encontrada.', 'danger')
        return redirect(url_for('turma.listar_turmas'))
    
    cargos_atuais = TurmaService.get_cargos_da_turma(turma_id, CARGOS_LISTA)
    
    return render_template('detalhes_turma.html', turma=turma, cargos_lista=CARGOS_LISTA,
                           cargos_atuais=cargos_atuais)

@turma_bp.route('/<int:turma_id>/salvar-cargos', methods=['POST'])
@login_required
@school_admin_or_programmer_required
def salvar_cargos_turma(turma_id):
    # O formulário WTForms não é mais necessário aqui, pois os dados vêm do modal
    success, message = TurmaService.atualizar_cargos(turma_id, request.form)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('turma.detalhes_turma', turma_id=turma_id))

@turma_bp.route('/cadastrar', methods=['GET', 'POST'])
@login_required
@school_admin_or_programmer_required
def cadastrar_turma():
    form = TurmaForm()
    
    school_id = UserService.get_current_school_id()
    if not school_id:
        flash('Não foi possível identificar a escola. Por favor, contate o suporte.', 'danger')
        return redirect(url_for('turma.listar_turmas'))

    alunos_sem_turma = db.session.scalars(
        select(Aluno).join(User).join(UserSchool).where(
            Aluno.turma_id.is_(None),
            UserSchool.school_id == school_id
        )
    ).all()
    form.alunos_ids.choices = [(a.id, f"{a.user.nome_completo} ({a.user.matricula})") for a in alunos_sem_turma]

    if form.validate_on_submit():
        success, message = TurmaService.create_turma(form.data, school_id)
        flash(message, 'success' if success else 'danger')
        if success:
            return redirect(url_for('turma.listar_turmas'))
    
    return render_template('cadastrar_turma.html', form=form)

@turma_bp.route('/editar/<int:turma_id>', methods=['GET', 'POST'])
@login_required
@school_admin_or_programmer_required
def editar_turma(turma_id):
    turma = db.session.get(Turma, turma_id)
    if not turma:
        flash('Turma não encontrada.', 'danger')
        return redirect(url_for('turma.listar_turmas'))
    
    form = TurmaForm(obj=turma)
    alunos_disponiveis = db.session.scalars(select(Aluno).join(User).where(or_(Aluno.turma_id.is_(None), Aluno.turma_id == turma_id)).order_by(User.nome_completo)).all()
    form.alunos_ids.choices = [(a.id, f"{a.user.nome_completo} ({a.user.matricula})") for a in alunos_disponiveis]
    
    if form.validate_on_submit():
        success, message = TurmaService.update_turma(turma_id, form.data)
        flash(message, 'success' if success else 'danger')
        if success:
            return redirect(url_for('turma.listar_turmas'))

    if request.method == 'GET':
        form.alunos_ids.data = [a.id for a in turma.alunos]

    return render_template('editar_turma.html', form=form, turma=turma)

@turma_bp.route('/excluir/<int:turma_id>', methods=['POST'])
@login_required
@school_admin_or_programmer_required
def excluir_turma(turma_id):
    form = DeleteForm()
    if form.validate_on_submit():
        success, message = TurmaService.delete_turma(turma_id)
        flash(message, 'success' if success else 'danger')
    else:
        flash('Falha na validação do token CSRF.', 'danger')
    return redirect(url_for('turma.listar_turmas'))