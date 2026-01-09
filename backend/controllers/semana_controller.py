# backend/controllers/semana_controller.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from sqlalchemy import select
from datetime import datetime
from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SubmitField, SelectField, BooleanField, IntegerField
from wtforms.validators import DataRequired, Optional, NumberRange
import json

from ..models.database import db
from ..models.semana import Semana
from ..models.horario import Horario
from ..models.ciclo import Ciclo
from utils.decorators import admin_or_programmer_required, school_admin_or_programmer_required
from ..services.semana_service import SemanaService
from ..services.user_service import UserService

semana_bp = Blueprint('semana', __name__, url_prefix='/semana')

class AddSemanaForm(FlaskForm):
    nome = StringField('Nome da Semana', validators=[DataRequired()])
    data_inicio = DateField('Data de Início', validators=[DataRequired()])
    data_fim = DateField('Data de Fim', validators=[DataRequired()])
    ciclo_id = SelectField('Ciclo', coerce=int, validators=[DataRequired()])
    mostrar_periodo_13 = BooleanField('13º Período')
    mostrar_periodo_14 = BooleanField('14º Período')
    mostrar_periodo_15 = BooleanField('15º Período')
    mostrar_sabado = BooleanField('Habilitar Sábado')
    periodos_sabado = IntegerField('Períodos Sábado', validators=[Optional(), NumberRange(min=1, max=15)])
    mostrar_domingo = BooleanField('Habilitar Domingo')
    periodos_domingo = IntegerField('Períodos Domingo', validators=[Optional(), NumberRange(min=1, max=15)])
    submit_add = SubmitField('Adicionar Semana')

class DeleteForm(FlaskForm):
    pass

@semana_bp.route('/')
@login_required
def index():
    return gerenciar_semanas(None)

@semana_bp.route('/gerenciar', defaults={'ciclo_id': None}, methods=['GET'])
@semana_bp.route('/gerenciar/<int:ciclo_id>', methods=['GET'])
@login_required
@school_admin_or_programmer_required
def gerenciar_semanas(ciclo_id):
    form = AddSemanaForm()
    delete_form = DeleteForm()
    
    school_id = UserService.get_current_school_id()
    
    # Busca apenas Ciclos da escola atual
    ciclos = db.session.execute(
        select(Ciclo).where(Ciclo.school_id == school_id).order_by(Ciclo.nome)
    ).scalars().all()
    
    form.ciclo_id.choices = [(c.id, c.nome) for c in ciclos]

    # Query: Semanas que pertencem a ciclos desta escola
    query = select(Semana).join(Ciclo).where(Ciclo.school_id == school_id).order_by(Semana.data_inicio.desc())
    
    if ciclo_id:
        # Validação extra: o ciclo pertence à escola?
        if any(c.id == ciclo_id for c in ciclos):
            query = query.where(Semana.ciclo_id == ciclo_id)
            form.ciclo_id.data = ciclo_id
        else:
            ciclo_id = None # Ciclo inválido ou de outra escola
    
    semanas = db.session.execute(query).scalars().all()

    return render_template('gerenciar_semanas.html', 
                           semanas=semanas, 
                           add_form=form, 
                           delete_form=delete_form,
                           todos_os_ciclos=ciclos, 
                           ciclo_selecionado_id=ciclo_id)

@semana_bp.route('/adicionar', methods=['POST'])
@login_required
@school_admin_or_programmer_required
def adicionar_semana():
    form = AddSemanaForm()
    school_id = UserService.get_current_school_id()
    
    ciclos = db.session.execute(
        select(Ciclo).where(Ciclo.school_id == school_id).order_by(Ciclo.nome)
    ).scalars().all()
    form.ciclo_id.choices = [(c.id, c.nome) for c in ciclos]

    if form.validate_on_submit():
        # Service valida se o ciclo pertence à escola
        success, message = SemanaService.add_semana(form.data)
        if success:
            flash(message, 'success')
        else:
            flash(message, 'danger')
        return redirect(url_for('semana.gerenciar_semanas', ciclo_id=form.ciclo_id.data))
    
    for field, errors in form.errors.items():
        for error in errors:
            flash(f"Erro em {getattr(form, field).label.text}: {error}", 'danger')
            
    ciclo_id = request.form.get('ciclo_id')
    return redirect(url_for('semana.gerenciar_semanas', ciclo_id=ciclo_id))

@semana_bp.route('/editar/<int:semana_id>', methods=['GET', 'POST'])
@login_required
@school_admin_or_programmer_required
def editar_semana(semana_id):
    semana = db.session.get(Semana, semana_id)
    school_id = UserService.get_current_school_id()
    
    # Validação de segurança via Ciclo
    if not semana or (school_id and semana.ciclo.school_id != school_id):
        flash("Semana não encontrada ou não pertence à sua escola.", "danger")
        return redirect(url_for('semana.gerenciar_semanas'))

    form = AddSemanaForm(obj=semana)
    ciclos = db.session.execute(
        select(Ciclo).where(Ciclo.school_id == school_id).order_by(Ciclo.nome)
    ).scalars().all()
    form.ciclo_id.choices = [(c.id, c.nome) for c in ciclos]

    if form.validate_on_submit():
        data = request.form.to_dict()
        data['ciclo_id'] = form.ciclo_id.data
        data.update({
             'mostrar_periodo_13': 'mostrar_periodo_13' in request.form,
             'mostrar_periodo_14': 'mostrar_periodo_14' in request.form,
             'mostrar_periodo_15': 'mostrar_periodo_15' in request.form,
             'mostrar_sabado': 'mostrar_sabado' in request.form,
             'mostrar_domingo': 'mostrar_domingo' in request.form
        })
        
        success, msg = SemanaService.update_semana(semana_id, data)
        if success:
            flash('Semana atualizada com sucesso!', 'success')
            return redirect(url_for('semana.gerenciar_semanas', ciclo_id=semana.ciclo_id))
        else:
            flash(msg, 'danger')

    return render_template('editar_semana.html', semana=semana, form=form)


@semana_bp.route('/deletar/<int:semana_id>', methods=['POST'])
@login_required
@school_admin_or_programmer_required
def deletar_semana(semana_id):
    form = DeleteForm()
    if form.validate_on_submit():
        semana = db.session.get(Semana, semana_id)
        if semana:
            ciclo_id = semana.ciclo_id
            success, message = SemanaService.delete_semana(semana_id)
            flash(message, 'success' if success else 'danger')
            return redirect(url_for('semana.gerenciar_semanas', ciclo_id=ciclo_id))
    flash('Ocorreu um erro ao tentar deletar.', 'danger')
    return redirect(url_for('semana.gerenciar_semanas'))

@semana_bp.route('/ciclo/adicionar', methods=['POST'])
@login_required
@admin_or_programmer_required
def adicionar_ciclo():
    nome_ciclo = request.form.get('nome_ciclo')
    school_id = UserService.get_current_school_id()
    
    if nome_ciclo and school_id:
        # Verifica se já existe ciclo com esse nome NA MESMA ESCOLA
        exists = db.session.scalar(
            select(Ciclo).where(Ciclo.nome == nome_ciclo, Ciclo.school_id == school_id)
        )
        if not exists:
            # CRIA O CICLO VINCULADO À ESCOLA
            db.session.add(Ciclo(nome=nome_ciclo, school_id=school_id))
            db.session.commit()
            flash(f"Ciclo '{nome_ciclo}' criado com sucesso!", "success")
        else:
            flash(f"Já existe um ciclo com o nome '{nome_ciclo}' nesta escola.", "danger")
    else:
        flash("Nome do ciclo inválido.", "danger")
    return redirect(url_for('semana.gerenciar_semanas'))

@semana_bp.route('/ciclo/deletar/<int:ciclo_id>', methods=['POST'])
@login_required
@admin_or_programmer_required
def deletar_ciclo(ciclo_id):
    # CORREÇÃO: Chama o Service que faz a limpeza em cascata
    success, message = SemanaService.deletar_ciclo(ciclo_id)
    
    category = 'success' if success else 'danger'
    flash(message, category)
    
    return redirect(url_for('semana.gerenciar_semanas'))

@semana_bp.route('/<int:semana_id>/salvar-prioridade', methods=['POST'])
@login_required
@school_admin_or_programmer_required
def salvar_prioridade(semana_id):
    try:
        semana = db.session.get(Semana, semana_id)
        school_id = UserService.get_current_school_id()
        
        if not semana or (school_id and semana.ciclo.school_id != school_id):
            return jsonify({'success': False, 'message': 'Semana não encontrada'}), 404

        data = request.get_json()
        semana.priority_active = data.get('status', False)
        
        disciplinas = data.get('disciplinas', [])
        semana.priority_disciplines = json.dumps(disciplinas)

        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500