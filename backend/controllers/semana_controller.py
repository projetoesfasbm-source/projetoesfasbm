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
    # Campos adicionados para períodos extras e fins de semana
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

@semana_bp.route('/gerenciar')
@login_required
@admin_or_programmer_required
def gerenciar_semanas():
    ciclo_selecionado_id = request.args.get('ciclo_id', type=int)
    todos_os_ciclos = db.session.scalars(select(Ciclo).order_by(Ciclo.nome)).all()

    if not ciclo_selecionado_id and todos_os_ciclos:
        ciclo_selecionado_id = todos_os_ciclos[0].id
    
    semanas = []
    if ciclo_selecionado_id:
        semanas = db.session.scalars(
            select(Semana).where(Semana.ciclo_id == ciclo_selecionado_id).order_by(Semana.data_inicio.desc())
        ).all()
    
    add_form = AddSemanaForm()
    if todos_os_ciclos:
        add_form.ciclo_id.choices = [(c.id, c.nome) for c in todos_os_ciclos]
    
    delete_form = DeleteForm()
    
    return render_template('gerenciar_semanas.html', 
                           semanas=semanas, 
                           todos_os_ciclos=todos_os_ciclos, 
                           ciclo_selecionado_id=ciclo_selecionado_id,
                           add_form=add_form,
                           delete_form=delete_form)

@semana_bp.route('/adicionar', methods=['POST'])
@login_required
@admin_or_programmer_required
def adicionar_semana():
    form = AddSemanaForm()
    ciclos = db.session.scalars(select(Ciclo).order_by(Ciclo.nome)).all()
    form.ciclo_id.choices = [(c.id, c.nome) for c in ciclos]

    if form.validate_on_submit():
        success, message = SemanaService.add_semana(form.data)
        flash(message, 'success' if success else 'danger')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Erro no campo '{getattr(form, field).label.text}': {error}", 'danger')
        if not form.errors:
            flash('Erro no formulário. Verifique os dados inseridos.', 'danger')
        
    return redirect(url_for('semana.gerenciar_semanas', ciclo_id=form.ciclo_id.data))


@semana_bp.route('/editar/<int:semana_id>', methods=['GET', 'POST'])
@login_required
@admin_or_programmer_required
def editar_semana(semana_id):
    semana = db.session.get(Semana, semana_id)
    if not semana:
        flash("Semana não encontrada.", "danger")
        return redirect(url_for('semana.gerenciar_semanas'))

    form = AddSemanaForm(obj=semana)
    ciclos = db.session.execute(select(Ciclo).order_by(Ciclo.nome)).scalars().all()
    form.ciclo_id.choices = [(c.id, c.nome) for c in ciclos]

    if form.validate_on_submit():
        semana.nome = form.nome.data
        semana.data_inicio = datetime.strptime(request.form['data_inicio'], '%Y-%m-%d').date()
        semana.data_fim = datetime.strptime(request.form['data_fim'], '%Y-%m-%d').date()
        semana.ciclo_id = form.ciclo_id.data
        semana.mostrar_periodo_13 = 'mostrar_periodo_13' in request.form
        semana.mostrar_periodo_14 = 'mostrar_periodo_14' in request.form
        semana.mostrar_periodo_15 = 'mostrar_periodo_15' in request.form
        semana.mostrar_sabado = 'mostrar_sabado' in request.form
        semana.periodos_sabado = int(request.form.get('periodos_sabado') or 0)
        semana.mostrar_domingo = 'mostrar_domingo' in request.form
        semana.periodos_domingo = int(request.form.get('periodos_domingo') or 0)
        
        db.session.commit()
        flash('Semana atualizada com sucesso!', 'success')
        return redirect(url_for('semana.gerenciar_semanas', ciclo_id=semana.ciclo_id))

    return render_template('editar_semana.html', semana=semana)


@semana_bp.route('/deletar/<int:semana_id>', methods=['POST'])
@login_required
@admin_or_programmer_required
def deletar_semana(semana_id):
    form = DeleteForm()
    if form.validate_on_submit():
        semana = db.session.get(Semana, semana_id)
        if semana:
            ciclo_id = semana.ciclo_id
            success, message = SemanaService.delete_semana(semana_id)
            flash(message, 'success' if success else 'danger')
            return redirect(url_for('semana.gerenciar_semanas', ciclo_id=ciclo_id))
    flash('Ocorreu um erro ao tentar deletar a semana.', 'danger')
    return redirect(url_for('semana.gerenciar_semanas'))

@semana_bp.route('/ciclo/adicionar', methods=['POST'])
@login_required
@admin_or_programmer_required
def adicionar_ciclo():
    nome_ciclo = request.form.get('nome_ciclo')
    if nome_ciclo:
        if not db.session.scalar(select(Ciclo).where(Ciclo.nome == nome_ciclo)):
            db.session.add(Ciclo(nome=nome_ciclo))
            db.session.commit()
            flash(f"Ciclo '{nome_ciclo}' criado com sucesso!", "success")
        else:
            flash(f"Já existe um ciclo com o nome '{nome_ciclo}'.", "danger")
    else:
        flash("O nome do ciclo não pode estar vazio.", "danger")
    return redirect(url_for('semana.gerenciar_semanas'))

@semana_bp.route('/ciclo/deletar/<int:ciclo_id>', methods=['POST'])
@login_required
@admin_or_programmer_required
def deletar_ciclo(ciclo_id):
    ciclo = db.session.get(Ciclo, ciclo_id)
    if ciclo:
        if ciclo.semanas or ciclo.disciplinas:
            flash("Não é possível deletar um ciclo que contém semanas ou disciplinas associadas.", "danger")
        else:
            db.session.delete(ciclo)
            db.session.commit()
            flash(f"Ciclo '{ciclo.nome}' deletado com sucesso.", "success")
    else:
        flash("Ciclo não encontrado.", "danger")
    return redirect(url_for('semana.gerenciar_semanas'))

# --- ROTA PARA SALVAR A PRIORIDADE (JSON/NAMES) ---
@semana_bp.route('/<int:semana_id>/salvar-prioridade', methods=['POST'])
@login_required
@school_admin_or_programmer_required
def salvar_prioridade(semana_id):
    try:
        semana = db.session.get(Semana, semana_id)
        if not semana:
            return jsonify({'success': False, 'message': 'Semana não encontrada'}), 404

        data = request.get_json()
        
        # Atualiza o status
        semana.priority_active = data.get('status', False)
        
        # Atualiza a lista de NOMES (agora salvamos JSON)
        disciplinas = data.get('disciplinas', [])
        semana.priority_disciplines = json.dumps(disciplinas)

        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500