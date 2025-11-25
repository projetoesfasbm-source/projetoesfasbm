# backend/controllers/vinculo_controller.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField
from wtforms.validators import DataRequired, Optional

from ..models.database import db
from ..models.instrutor import Instrutor
from ..models.turma import Turma
from ..models.disciplina import Disciplina
from ..models.disciplina_turma import DisciplinaTurma
from ..models.user import User
from ..models.ciclo import Ciclo
from ..services.user_service import UserService 
from ..services.vinculo_service import VinculoService
from ..services.instrutor_service import InstrutorService
from ..services.turma_service import TurmaService
from utils.decorators import admin_or_programmer_required, school_admin_or_programmer_required

vinculo_bp = Blueprint('vinculo', __name__, url_prefix='/vinculos')

class VinculoForm(FlaskForm):
    instrutor_id_1 = SelectField('Instrutor 1', coerce=int, validators=[Optional()])
    instrutor_id_2 = SelectField('Instrutor 2', coerce=int, validators=[Optional()])
    disciplina_id = SelectField('Disciplina', coerce=int, validators=[DataRequired(message="Por favor, selecione uma disciplina.")])
    submit = SubmitField('Salvar')

class DeleteForm(FlaskForm):
    pass

@vinculo_bp.route('/')
@login_required
@admin_or_programmer_required
def gerenciar_vinculos():
    turma_filtrada_id = request.args.get('turma_id', type=int)
    
    school_id = UserService.get_current_school_id()
    if not school_id:
        flash("Nenhuma escola associada ou selecionada.", "warning")
        return redirect(url_for('main.dashboard'))

    # CORREÇÃO:
    # Se houver filtro de turma, valida se ela pertence à escola.
    if turma_filtrada_id:
        turma_check = db.session.get(Turma, turma_filtrada_id)
        if not turma_check or turma_check.school_id != school_id:
            flash("Turma selecionada inválida.", "warning")
            turma_filtrada_id = None # Reseta o filtro se inválido

    # Chama o serviço passando a turma (se houver) E o ID da escola.
    # O Service agora sabe filtrar por escola se a turma for None.
    vinculos = VinculoService.get_all_vinculos(turma_filtrada_id, school_id)
    
    turmas = TurmaService.get_turmas_by_school(school_id)
    
    delete_form = DeleteForm()
    
    return render_template('gerenciar_vinculos.html', 
                           vinculos=vinculos, 
                           turmas=turmas,
                           turma_filtrada_id=turma_filtrada_id,
                           delete_form=delete_form)

@vinculo_bp.route('/adicionar', methods=['GET', 'POST'])
@login_required
@school_admin_or_programmer_required
def adicionar_vinculo():
    form = VinculoForm()
    school_id = UserService.get_current_school_id()
    
    # ALTERAÇÃO: Usa o método sem paginação para carregar TODOS os instrutores
    instrutores = InstrutorService.get_all_instrutores_sem_paginacao(user=current_user)
    
    turmas = TurmaService.get_turmas_by_school(school_id)

    instrutor_choices = []
    for i in instrutores:
        nome = i.user.nome_de_guerra or i.user.username
        posto = i.user.posto_graduacao
        display_text = f"{nome} - {posto}" if posto else nome
        instrutor_choices.append((i.id, display_text))

    form.instrutor_id_1.choices = [(0, '-- Nenhum --')] + instrutor_choices
    form.instrutor_id_2.choices = [(0, '-- Nenhum --')] + instrutor_choices
    
    if request.method == 'POST':
        turma_id_selecionada = request.form.get('turma_id', type=int)
        turma_check = db.session.get(Turma, turma_id_selecionada)
        if turma_id_selecionada and turma_check and turma_check.school_id == school_id:
            disciplinas_da_turma = db.session.scalars(
                select(Disciplina).where(Disciplina.turma_id == turma_id_selecionada).order_by(Disciplina.materia)
            ).all()
            form.disciplina_id.choices = [(d.id, d.materia) for d in disciplinas_da_turma]
        else:
            form.disciplina_id.choices = []
    else:
        form.disciplina_id.choices = []

    if form.validate_on_submit():
        success, message = VinculoService.add_vinculo(form.data)
        flash(message, 'success' if success else 'danger')
        if success:
            return redirect(url_for('vinculo.gerenciar_vinculos'))
    elif form.errors:
        for field, error_messages in form.errors.items():
            for error in error_messages:
                flash(f"Erro no campo '{getattr(form, field).label.text}': {error}", 'danger')
    
    return render_template('adicionar_vinculo.html', form=form, turmas=turmas)


@vinculo_bp.route('/editar/<int:vinculo_id>', methods=['GET', 'POST'])
@login_required
@school_admin_or_programmer_required
def editar_vinculo(vinculo_id):
    school_id = UserService.get_current_school_id()
    vinculo = db.session.get(DisciplinaTurma, vinculo_id)

    if not vinculo:
        flash("Vínculo não encontrado.", "danger")
        return redirect(url_for('vinculo.gerenciar_vinculos'))
        
    turma_atual = db.session.scalar(select(Turma).where(Turma.nome == vinculo.pelotao))
    if not turma_atual or turma_atual.school_id != school_id:
        flash("Este vínculo não pertence à sua escola.", "danger")
        return redirect(url_for('vinculo.gerenciar_vinculos'))

    form = VinculoForm(obj=vinculo)
    
    # ALTERAÇÃO: Usa o método sem paginação para carregar TODOS os instrutores na edição também
    instrutores = InstrutorService.get_all_instrutores_sem_paginacao(user=current_user)
    
    instrutor_choices = []
    for i in instrutores:
        nome = i.user.nome_de_guerra or i.user.username
        posto = i.user.posto_graduacao
        display_text = f"{nome} - {posto}" if posto else nome
        instrutor_choices.append((i.id, display_text))

    form.instrutor_id_1.choices = [(0, '-- Nenhum --')] + instrutor_choices
    form.instrutor_id_2.choices = [(0, '-- Nenhum --')] + instrutor_choices

    if turma_atual:
        form.disciplina_id.choices = [(d.id, d.materia) for d in turma_atual.disciplinas]
    
    if form.validate_on_submit():
        success, message = VinculoService.edit_vinculo(vinculo_id, form.data)
        flash(message, 'success' if success else 'danger')
        return redirect(url_for('vinculo.gerenciar_vinculos', turma_id=turma_atual.id))
    
    if request.method == 'GET':
        form.instrutor_id_1.data = vinculo.instrutor_id_1 or 0
        form.instrutor_id_2.data = vinculo.instrutor_id_2 or 0
        form.disciplina_id.data = vinculo.disciplina_id

    return render_template('editar_vinculo.html', form=form, vinculo=vinculo, turma=turma_atual)

@vinculo_bp.route('/excluir/<int:vinculo_id>', methods=['POST'])
@login_required
@school_admin_or_programmer_required
def excluir_vinculo(vinculo_id):
    school_id = UserService.get_current_school_id()
    vinculo = db.session.get(DisciplinaTurma, vinculo_id)

    turma_id_para_redirecionar = None
    if not vinculo:
        flash("Vínculo não encontrado.", "danger")
        return redirect(url_for('vinculo.gerenciar_vinculos'))
        
    turma_atual = db.session.scalar(select(Turma).where(Turma.nome == vinculo.pelotao))
    if not turma_atual or turma_atual.school_id != school_id:
        flash("Este vínculo não pertence à sua escola.", "danger")
        return redirect(url_for('vinculo.gerenciar_vinculos'))
    
    turma_id_para_redirecionar = turma_atual.id

    form = DeleteForm()
    if form.validate_on_submit():
        success, message = VinculoService.delete_vinculo(vinculo_id)
        flash(message, 'success' if success else 'danger')
        
    return redirect(url_for('vinculo.gerenciar_vinculos', turma_id=turma_id_para_redirecionar))