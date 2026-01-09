# backend/controllers/disciplina_controller.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_required, current_user
from sqlalchemy import select, func, desc
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField, SelectField, SelectMultipleField
from wtforms.validators import DataRequired, Length, NumberRange, Optional
from wtforms.widgets import CheckboxInput, ListWidget
from datetime import timedelta 

from ..models.database import db
from ..models.disciplina import Disciplina
from ..models.ciclo import Ciclo
from ..models.turma import Turma
from ..models.horario import Horario
from ..models.semana import Semana
from ..services.disciplina_service import DisciplinaService
from ..services.turma_service import TurmaService
from ..services.user_service import UserService
from utils.decorators import admin_or_programmer_required, school_admin_or_programmer_required, can_view_management_pages_required

disciplina_bp = Blueprint('disciplina', __name__, url_prefix='/disciplina')

class DisciplinaForm(FlaskForm):
    materia = StringField('Matéria', validators=[DataRequired(), Length(min=3, max=100)])
    carga_horaria_prevista = IntegerField('Carga Horária Total Prevista', validators=[DataRequired(), NumberRange(min=1)])
    carga_horaria_cumprida = IntegerField('Carga Horária Já Cumprida (Legado)', validators=[Optional(), NumberRange(min=0)], default=0)
    ciclo_id = SelectField('Ciclo', coerce=int, validators=[DataRequired()])
    
    # CORREÇÃO 1: Removido DataRequired daqui para evitar o bug do HTML5 exigir todos os checkboxes
    turma_ids = SelectMultipleField(
        'Turmas', 
        coerce=int, 
        validators=[Optional()], # Alterado para Optional para não travar no navegador
        option_widget=CheckboxInput(), 
        widget=ListWidget(prefix_label=False)
    )
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
    
    turmas_disponiveis = TurmaService.get_turmas_by_school(school_id)
    todas_disciplinas = DisciplinaService.get_disciplinas_by_school(school_id)

    disciplinas_filtradas = []
    if turma_selecionada_id:
        disciplinas_filtradas = [d for d in todas_disciplinas if d.turma_id == turma_selecionada_id]
    else:
        disciplinas_filtradas = todas_disciplinas

    disciplinas_com_progresso = []
    for d in disciplinas_filtradas:
        progresso = DisciplinaService.get_dados_progresso(d) 
        disciplinas_com_progresso.append({'disciplina': d, 'progresso': progresso})

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
    
    # CORREÇÃO 2: Filtrar ciclos apenas da escola atual
    ciclos = db.session.scalars(
        select(Ciclo).where(Ciclo.school_id == school_id).order_by(Ciclo.nome)
    ).all()
    form.ciclo_id.choices = [(c.id, c.nome) for c in ciclos]
    
    turmas = TurmaService.get_turmas_by_school(school_id)
    form.turma_ids.choices = [(t.id, t.nome) for t in turmas]
    
    if form.validate_on_submit():
        # Validação manual para garantir que pelo menos uma turma foi selecionada
        if not form.turma_ids.data:
            flash("Selecione pelo menos uma turma.", "warning")
            return render_template('adicionar_disciplina.html', form=form)

        success, message = DisciplinaService.create_disciplina(form.data, school_id)
        flash(message, 'success' if success else 'danger')
        if success:
            return redirect(url_for('disciplina.listar_disciplinas'))

    return render_template('adicionar_disciplina.html', form=form)


@disciplina_bp.route('/editar/<int:disciplina_id>', methods=['GET', 'POST'])
@login_required
@school_admin_or_programmer_required
def editar_disciplina(disciplina_id):
    disciplina = db.session.get(Disciplina, disciplina_id)
    school_id = UserService.get_current_school_id() # Necessário para o filtro

    if not disciplina:
        flash('Disciplina não encontrada.', 'danger')
        return redirect(url_for('disciplina.listar_disciplinas'))

    # Verifica se a disciplina pertence à escola atual (segurança)
    if school_id and disciplina.turma.school_id != school_id:
        flash('Permissão negada.', 'danger')
        return redirect(url_for('disciplina.listar_disciplinas'))

    class EditDisciplinaForm(FlaskForm):
        materia = StringField('Matéria', validators=[DataRequired(), Length(min=3, max=100)])
        carga_horaria_prevista = IntegerField('Carga Horária Total Prevista', validators=[DataRequired(), NumberRange(min=1)])
        carga_horaria_cumprida = IntegerField('Carga Horária Cumprida', validators=[Optional(), NumberRange(min=0)], default=0)
        ciclo_id = SelectField('Ciclo', coerce=int, validators=[DataRequired()])
        turma_id = SelectField('Turma', coerce=int, validators=[DataRequired(message="A turma é obrigatória.")])
        submit = SubmitField('Salvar')

    form = EditDisciplinaForm(obj=disciplina)
    
    # CORREÇÃO 2: Filtrar ciclos apenas da escola atual também na edição
    ciclos = db.session.scalars(
        select(Ciclo).where(Ciclo.school_id == school_id).order_by(Ciclo.nome)
    ).all()
    form.ciclo_id.choices = [(c.id, c.nome) for c in ciclos]
    
    # No edit, a turma é fixa ou única, mantendo lógica original
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
        
        # Segurança extra antes de excluir
        school_id = UserService.get_current_school_id()
        if disciplina and school_id and disciplina.turma.school_id != school_id:
             flash('Permissão negada.', 'danger')
             return redirect(url_for('disciplina.listar_disciplinas'))

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

# --- ROTA DE AUDITORIA COM CÁLCULO DE HORAS RESTANTES ---
@disciplina_bp.route('/detalhes/<int:disciplina_id>')
@login_required
def detalhes_disciplina(disciplina_id):
    disciplina = db.session.get(Disciplina, disciplina_id)
    if not disciplina:
        flash('Disciplina não encontrada.', 'danger')
        return redirect(url_for('disciplina.listar_disciplinas'))
    
    # 1. Busca TODOS os horários brutos
    raw_agendamentos = db.session.scalars(
        select(Horario)
        .join(Semana, Horario.semana_id == Semana.id)
        .where(Horario.disciplina_id == disciplina_id)
    ).all()
    
    mapa_dias = {
        'segunda': 0, 'segunda-feira': 0, 
        'terça': 1, 'terca': 1, 'terça-feira': 1, 'terca-feira': 1,
        'quarta': 2, 'quarta-feira': 2,
        'quinta': 3, 'quinta-feira': 3,
        'sexta': 4, 'sexta-feira': 4,
        'sábado': 5, 'sabado': 5, 'sábado-feira': 5,
        'domingo': 6, 'domingo-feira': 6
    }

    processed_items = []
    total_tempos_agendados = 0

    # 2. Pré-processamento
    for agendamento in raw_agendamentos:
        qtd = agendamento.duracao if agendamento.duracao else 1
        total_tempos_agendados += qtd
        
        instrutor_nome = 'Não definido'
        if agendamento.instrutor and agendamento.instrutor.user:
            posto = agendamento.instrutor.user.posto_graduacao or ''
            nome = agendamento.instrutor.user.nome_de_guerra or agendamento.instrutor.user.nome_completo
            instrutor_nome = f"{posto} {nome}".strip()

        data_real = agendamento.semana.data_inicio
        dia_text = agendamento.dia_semana.lower().strip() if agendamento.dia_semana else ""
        offset = mapa_dias.get(dia_text)
        if offset is not None:
             data_real = agendamento.semana.data_inicio + timedelta(days=offset)

        processed_items.append({
            'id': agendamento.id,
            'data_real': data_real,
            'periodo_inicio': agendamento.periodo,
            'periodo_fim': agendamento.periodo + qtd - 1,
            'qtd': qtd,
            'semana_nome': agendamento.semana.nome,
            'semana_id': agendamento.semana.id,
            'pelotao': agendamento.pelotao,
            'instrutor_nome': instrutor_nome
        })

    # 3. Ordenação
    processed_items.sort(key=lambda x: (x['data_real'], -x['periodo_inicio']), reverse=True)

    # 4. Agrupamento
    grouped_list = []
    if processed_items:
        current_block = processed_items[0]
        
        for i in range(1, len(processed_items)):
            next_item = processed_items[i]
            
            is_same_day = (current_block['data_real'] == next_item['data_real'])
            is_same_instr = (current_block['instrutor_nome'] == next_item['instrutor_nome'])
            is_continuous = (current_block['periodo_fim'] + 1 == next_item['periodo_inicio'])
            
            if is_same_day and is_same_instr and is_continuous:
                current_block['periodo_fim'] = next_item['periodo_fim']
                current_block['qtd'] += next_item['qtd']
            else:
                grouped_list.append(current_block)
                current_block = next_item
        
        grouped_list.append(current_block)

    # 5. Formatação Final
    final_output = []
    for item in grouped_list:
        p_str = f"{item['periodo_inicio']}º"
        if item['periodo_inicio'] != item['periodo_fim']:
            p_str = f"{item['periodo_inicio']}º a {item['periodo_fim']}º"
            
        final_output.append({
            'id': item['id'],
            'data': item['data_real'],
            'semana': item['semana_nome'],
            'semana_id': item['semana_id'],
            'pelotao': item['pelotao'],
            'periodos': p_str,
            'qtd': item['qtd'],
            'instrutor': item['instrutor_nome']
        })
    
    # CÁLCULO FINAL DE HORAS RESTANTES
    horas_restantes = disciplina.carga_horaria_prevista - total_tempos_agendados
    
    return render_template(
        'detalhes_disciplina.html', 
        disciplina=disciplina, 
        agendamentos=final_output,
        total_auditado=total_tempos_agendados,
        horas_restantes=horas_restantes  # Passando para o template
    )