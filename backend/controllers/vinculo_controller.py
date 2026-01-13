# backend/controllers/vinculo_controller.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
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
# Removidos decoradores restritivos para usarmos verificação manual e precisa
from utils.decorators import can_view_management_pages_required

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
@can_view_management_pages_required
def gerenciar_vinculos():
    school_id = UserService.get_current_school_id()
    if not school_id:
        flash("Nenhuma escola associada ou selecionada.", "warning")
        return redirect(url_for('main.dashboard'))

    # PERMISSÃO: SENS, Admin Escola ou Programador
    # O método is_sens_in_school já retorna True para Admin Escola também.
    if not (current_user.is_programador or current_user.is_sens_in_school(school_id)):
        flash("Permissão negada. Apenas SENS ou Comando podem gerenciar vínculos.", "danger")
        return redirect(url_for('main.dashboard'))

    turma_filtrada_id = request.args.get('turma_id', type=int)
    
    if turma_filtrada_id:
        turma_check = db.session.get(Turma, turma_filtrada_id)
        if not turma_check or turma_check.school_id != school_id:
            flash("Turma selecionada inválida ou de outra escola.", "warning")
            turma_filtrada_id = None 

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
def adicionar_vinculo():
    school_id = UserService.get_current_school_id()
    if not school_id:
        return redirect(url_for('main.dashboard'))

    # PERMISSÃO
    if not (current_user.is_programador or current_user.is_sens_in_school(school_id)):
        flash("Permissão negada.", "danger")
        return redirect(url_for('vinculo.gerenciar_vinculos'))

    form = VinculoForm()
    
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
    
    # Carregamento dinâmico de disciplinas
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
def editar_vinculo(vinculo_id):
    school_id = UserService.get_current_school_id()
    if not school_id:
        return redirect(url_for('main.dashboard'))

    # PERMISSÃO DE ACESSO
    if not (current_user.is_programador or current_user.is_sens_in_school(school_id)):
        flash("Permissão negada. Você não tem permissão para editar vínculos.", "danger")
        return redirect(url_for('vinculo.gerenciar_vinculos'))

    vinculo = db.session.get(DisciplinaTurma, vinculo_id)

    if not vinculo:
        flash("Vínculo não encontrado.", "danger")
        return redirect(url_for('vinculo.gerenciar_vinculos'))
        
    # --- CORREÇÃO CRÍTICA DA VALIDAÇÃO DA TURMA ---
    # Tenta recuperar a turma de forma segura, priorizando o relacionamento direto/ID
    turma_atual = None
    
    # 1. Tenta pelo relacionamento direto (se existir no modelo)
    if hasattr(vinculo, 'turma') and vinculo.turma:
        turma_atual = vinculo.turma
        
    # 2. Se falhar, tenta pelo ID da turma armazenado
    elif hasattr(vinculo, 'turma_id') and vinculo.turma_id:
        turma_atual = db.session.get(Turma, vinculo.turma_id)
    
    # 3. Fallback: Se não tiver ID, tenta pelo nome (string 'pelotao'), 
    #    mas filtrando EXPLICITAMENTE pela escola atual para evitar conflito de nomes.
    if not turma_atual and vinculo.pelotao:
        turma_atual = db.session.scalar(
            select(Turma).where(
                Turma.nome == vinculo.pelotao,
                Turma.school_id == school_id
            )
        )

    # Se após todas as tentativas não acharmos a turma OU a turma não for desta escola:
    if not turma_atual or turma_atual.school_id != school_id:
        flash("Este vínculo pertence a uma turma que não está nesta escola ou foi removida.", "danger")
        return redirect(url_for('vinculo.gerenciar_vinculos'))

    form = VinculoForm(obj=vinculo)
    
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
def excluir_vinculo(vinculo_id):
    school_id = UserService.get_current_school_id()
    if not school_id:
        return redirect(url_for('main.dashboard'))

    # PERMISSÃO
    if not (current_user.is_programador or current_user.is_sens_in_school(school_id)):
        flash("Permissão negada.", "danger")
        return redirect(url_for('vinculo.gerenciar_vinculos'))

    vinculo = db.session.get(DisciplinaTurma, vinculo_id)

    if not vinculo:
        flash("Vínculo não encontrado.", "danger")
        return redirect(url_for('vinculo.gerenciar_vinculos'))
        
    # --- MESMA CORREÇÃO DE VALIDAÇÃO PARA EXCLUSÃO ---
    turma_atual = None
    if hasattr(vinculo, 'turma') and vinculo.turma:
        turma_atual = vinculo.turma
    elif hasattr(vinculo, 'turma_id') and vinculo.turma_id:
        turma_atual = db.session.get(Turma, vinculo.turma_id)
    
    if not turma_atual and vinculo.pelotao:
        turma_atual = db.session.scalar(
            select(Turma).where(
                Turma.nome == vinculo.pelotao,
                Turma.school_id == school_id
            )
        )
    
    if not turma_atual or turma_atual.school_id != school_id:
        flash("Este vínculo pertence a uma turma que não está nesta escola.", "danger")
        return redirect(url_for('vinculo.gerenciar_vinculos'))
    
    turma_id_para_redirecionar = turma_atual.id

    form = DeleteForm()
    if form.validate_on_submit():
        success, message = VinculoService.delete_vinculo(vinculo_id)
        flash(message, 'success' if success else 'danger')
        
    return redirect(url_for('vinculo.gerenciar_vinculos', turma_id=turma_id_para_redirecionar))