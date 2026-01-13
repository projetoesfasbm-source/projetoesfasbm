from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import select
from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField
from wtforms.validators import DataRequired, Optional

from ..models.database import db
from ..models.turma import Turma
from ..models.disciplina import Disciplina
from ..models.disciplina_turma import DisciplinaTurma
from ..services.user_service import UserService 
from ..services.vinculo_service import VinculoService
from ..services.instrutor_service import InstrutorService
from ..services.turma_service import TurmaService
from utils.decorators import can_view_management_pages_required

vinculo_bp = Blueprint('vinculo', __name__, url_prefix='/vinculos')

class VinculoForm(FlaskForm):
    instrutor_id_1 = SelectField('Instrutor 1', coerce=int, validators=[Optional()])
    instrutor_id_2 = SelectField('Instrutor 2', coerce=int, validators=[Optional()])
    disciplina_id = SelectField('Disciplina', coerce=int, validators=[DataRequired(message="Por favor, selecione uma disciplina.")])
    submit = SubmitField('Salvar')

class DeleteForm(FlaskForm):
    pass

def check_permission(school_id):
    """
    Centraliza a verificação:
    Retorna True se for Programador, Admin Escola ou Chefe SENS (admin_sens).
    """
    if not school_id:
        return False
    
    # Programador tem acesso total
    if current_user.is_programador:
        return True
        
    # Verifica cargo na escola específica
    return current_user.is_sens_in_school(school_id)

@vinculo_bp.route('/')
@login_required
@can_view_management_pages_required
def gerenciar_vinculos():
    school_id = UserService.get_current_school_id()
    if not school_id:
        flash("Nenhuma escola selecionada.", "warning")
        return redirect(url_for('main.dashboard'))

    # Validação de Segurança
    if not check_permission(school_id):
        flash("Acesso restrito a Chefia de Ensino (SENS) ou Comando.", "danger")
        return redirect(url_for('main.dashboard'))

    turma_filtrada_id = request.args.get('turma_id', type=int)
    
    # Filtro de turma (apenas visual)
    if turma_filtrada_id:
        turma_check = db.session.get(Turma, turma_filtrada_id)
        if not turma_check or turma_check.school_id != school_id:
            flash("Turma inválida.", "warning")
            turma_filtrada_id = None 

    vinculos = VinculoService.get_all_vinculos(turma_filtrada_id, school_id)
    turmas = TurmaService.get_turmas_by_school(school_id)
    delete_form = DeleteForm()
    
    # Passamos a flag explicitamente para o template
    return render_template('gerenciar_vinculos.html', 
                           vinculos=vinculos, 
                           turmas=turmas,
                           turma_filtrada_id=turma_filtrada_id,
                           delete_form=delete_form,
                           can_manage_vinculos=True)

@vinculo_bp.route('/adicionar', methods=['GET', 'POST'])
@login_required
def adicionar_vinculo():
    school_id = UserService.get_current_school_id()
    if not check_permission(school_id):
        flash("Permissão negada.", "danger")
        return redirect(url_for('vinculo.gerenciar_vinculos'))

    form = VinculoForm()
    instrutores = InstrutorService.get_all_instrutores_sem_paginacao(user=current_user)
    turmas = TurmaService.get_turmas_by_school(school_id)

    # Popula instrutores
    instrutor_choices = []
    for i in instrutores:
        nome = i.user.nome_de_guerra or i.user.username
        posto = i.user.posto_graduacao
        display = f"{nome} - {posto}" if posto else nome
        instrutor_choices.append((i.id, display))

    form.instrutor_id_1.choices = [(0, '-- Nenhum --')] + instrutor_choices
    form.instrutor_id_2.choices = [(0, '-- Nenhum --')] + instrutor_choices
    
    # Lógica dinâmica de disciplinas via POST
    if request.method == 'POST':
        turma_id = request.form.get('turma_id', type=int)
        # Valida se a turma é da escola
        turma = db.session.get(Turma, turma_id)
        if turma and turma.school_id == school_id:
            disciplinas = db.session.scalars(
                select(Disciplina).where(Disciplina.turma_id == turma_id).order_by(Disciplina.materia)
            ).all()
            form.disciplina_id.choices = [(d.id, d.materia) for d in disciplinas]
        else:
            form.disciplina_id.choices = []
    else:
        form.disciplina_id.choices = []

    if form.validate_on_submit():
        success, message = VinculoService.add_vinculo(form.data)
        flash(message, 'success' if success else 'danger')
        if success:
            return redirect(url_for('vinculo.gerenciar_vinculos'))
    
    return render_template('adicionar_vinculo.html', form=form, turmas=turmas)


@vinculo_bp.route('/editar/<int:vinculo_id>', methods=['GET', 'POST'])
@login_required
def editar_vinculo(vinculo_id):
    school_id = UserService.get_current_school_id()
    if not check_permission(school_id):
        flash("Permissão negada.", "danger")
        return redirect(url_for('vinculo.gerenciar_vinculos'))

    vinculo = db.session.get(DisciplinaTurma, vinculo_id)
    if not vinculo:
        flash("Vínculo não encontrado.", "danger")
        return redirect(url_for('vinculo.gerenciar_vinculos'))
    
    # --- CORREÇÃO DEFINITIVA DE VALIDAÇÃO ---
    # 1. Obtemos a disciplina vinculada
    # 2. Obtemos a turma dessa disciplina
    # 3. Validamos se a turma pertence à escola atual
    # NÃO usamos vinculo.pelotao (string) para validação.
    
    if not vinculo.disciplina:
        flash("Erro crítico: Vínculo sem disciplina associada.", "danger")
        return redirect(url_for('vinculo.gerenciar_vinculos'))

    turma_real = vinculo.disciplina.turma
    
    if not turma_real or turma_real.school_id != school_id:
        flash("Este vínculo pertence a uma turma de outra escola.", "danger")
        return redirect(url_for('vinculo.gerenciar_vinculos'))

    form = VinculoForm(obj=vinculo)
    
    # Recarrega opções de instrutores
    instrutores = InstrutorService.get_all_instrutores_sem_paginacao(user=current_user)
    instrutor_choices = []
    for i in instrutores:
        nome = i.user.nome_de_guerra or i.user.username
        posto = i.user.posto_graduacao
        display = f"{nome} - {posto}" if posto else nome
        instrutor_choices.append((i.id, display))

    form.instrutor_id_1.choices = [(0, '-- Nenhum --')] + instrutor_choices
    form.instrutor_id_2.choices = [(0, '-- Nenhum --')] + instrutor_choices
    
    # Carrega disciplinas da turma REAL (via ID)
    form.disciplina_id.choices = [(d.id, d.materia) for d in turma_real.disciplinas]
    
    if form.validate_on_submit():
        success, message = VinculoService.edit_vinculo(vinculo_id, form.data)
        flash(message, 'success' if success else 'danger')
        return redirect(url_for('vinculo.gerenciar_vinculos', turma_id=turma_real.id))
    
    if request.method == 'GET':
        form.instrutor_id_1.data = vinculo.instrutor_id_1 or 0
        form.instrutor_id_2.data = vinculo.instrutor_id_2 or 0
        form.disciplina_id.data = vinculo.disciplina_id

    return render_template('editar_vinculo.html', form=form, vinculo=vinculo, turma=turma_real)

@vinculo_bp.route('/excluir/<int:vinculo_id>', methods=['POST'])
@login_required
def excluir_vinculo(vinculo_id):
    school_id = UserService.get_current_school_id()
    if not check_permission(school_id):
        flash("Permissão negada.", "danger")
        return redirect(url_for('vinculo.gerenciar_vinculos'))

    vinculo = db.session.get(DisciplinaTurma, vinculo_id)
    if not vinculo:
        flash("Vínculo não encontrado.", "danger")
        return redirect(url_for('vinculo.gerenciar_vinculos'))
        
    # Validação segura via ID Relacional
    if not vinculo.disciplina or not vinculo.disciplina.turma:
        flash("Vínculo corrompido (sem disciplina/turma). Exclusão forçada recomendada via banco.", "danger")
        return redirect(url_for('vinculo.gerenciar_vinculos'))

    turma_id = vinculo.disciplina.turma_id
    if vinculo.disciplina.turma.school_id != school_id:
        flash("Este vínculo pertence a outra escola.", "danger")
        return redirect(url_for('vinculo.gerenciar_vinculos'))

    form = DeleteForm()
    if form.validate_on_submit():
        success, message = VinculoService.delete_vinculo(vinculo_id)
        flash(message, 'success' if success else 'danger')
        
    return redirect(url_for('vinculo.gerenciar_vinculos', turma_id=turma_id))