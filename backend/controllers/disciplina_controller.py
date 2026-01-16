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
    
    turma_ids = SelectMultipleField(
        'Turmas', 
        coerce=int, 
        validators=[Optional()],
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
        # Se não selecionar turma, não mostra nada na lista principal para não sobrecarregar,
        # ou mostra tudo se for comportamento desejado. O template pede seleção.
        disciplinas_filtradas = [] 

    # Ordenação
    disciplinas_filtradas.sort(key=lambda d: d.materia)

    # Preparar dados de progresso para o template original
    disciplinas_com_progresso = []
    for d in disciplinas_filtradas:
        progresso = DisciplinaService.get_dados_progresso(d) 
        disciplinas_com_progresso.append({'disciplina': d, 'progresso': progresso})

    delete_form = DeleteForm()
    
    # Busca Ciclos para o filtro do dashboard (passado no contexto)
    ciclos = db.session.scalars(select(Ciclo).where(Ciclo.school_id == school_id)).all()
    
    return render_template('listar_disciplinas.html', 
                           disciplinas_com_progresso=disciplinas_com_progresso, # Variável chave para o template
                           delete_form=delete_form,
                           turmas=turmas_disponiveis,
                           turma_selecionada_id=turma_selecionada_id,
                           ciclos=ciclos)

@disciplina_bp.route('/dashboard-intelligence')
@login_required
@can_view_management_pages_required
def dashboard_disciplinas():
    """Rota exclusiva para o novo Dashboard"""
    school_id = UserService.get_current_school_id()
    if not school_id:
        return redirect(url_for('disciplina.listar_disciplinas'))

    ciclo_id_arg = request.args.get('ciclo_id')
    ciclos = db.session.scalars(select(Ciclo).where(Ciclo.school_id == school_id)).all()
    ciclo_selecionado_id = int(ciclo_id_arg) if ciclo_id_arg else (ciclos[-1].id if ciclos else None)

    dashboard_data = DisciplinaService.get_dashboard_data(school_id, ciclo_selecionado_id)

    return render_template('disciplinas_dashboard.html',
                           dashboard_data=dashboard_data,
                           ciclos=ciclos,
                           ciclo_selecionado_id=ciclo_selecionado_id)

@disciplina_bp.route('/adicionar', methods=['GET', 'POST'])
@login_required
@school_admin_or_programmer_required
def adicionar_disciplina():
    school_id = UserService.get_current_school_id()
    if not school_id:
        flash('Nenhuma escola associada.', 'danger')
        return redirect(url_for('disciplina.listar_disciplinas'))
        
    form = DisciplinaForm()
    
    ciclos = db.session.scalars(select(Ciclo).where(Ciclo.school_id == school_id).order_by(Ciclo.nome)).all()
    form.ciclo_id.choices = [(c.id, c.nome) for c in ciclos]
    
    turmas = TurmaService.get_turmas_by_school(school_id)
    form.turma_ids.choices = [(t.id, t.nome) for t in turmas]
    
    if form.validate_on_submit():
        if not form.turma_ids.data:
            flash("Selecione pelo menos uma turma.", "warning")
            return render_template('adicionar_disciplina.html', form=form)

        success_count = 0
        try:
            for t_id in form.turma_ids.data:
                data = {
                    'materia': form.materia.data,
                    'carga_horaria_prevista': form.carga_horaria_prevista.data,
                    'turma_id': t_id,
                    'ciclo_id': form.ciclo_id.data,
                    'instrutor_id': None 
                }
                DisciplinaService.create_disciplina(data)
                success_count += 1
            
            flash(f'{success_count} disciplinas criadas com sucesso!', 'success')
            return redirect(url_for('disciplina.listar_disciplinas', turma_id=form.turma_ids.data[0]))
        except Exception as e:
            flash(f'Erro ao criar disciplinas: {e}', 'danger')

    return render_template('adicionar_disciplina.html', form=form)

@disciplina_bp.route('/editar/<int:disciplina_id>', methods=['GET', 'POST'])
@login_required
@school_admin_or_programmer_required
def editar_disciplina(disciplina_id):
    disciplina = db.session.get(Disciplina, disciplina_id)
    school_id = UserService.get_current_school_id()

    if not disciplina or (school_id and disciplina.turma.school_id != school_id):
        flash('Disciplina não encontrada ou permissão negada.', 'danger')
        return redirect(url_for('disciplina.listar_disciplinas'))

    class EditDisciplinaForm(FlaskForm):
        materia = StringField('Matéria', validators=[DataRequired(), Length(min=3, max=100)])
        carga_horaria_prevista = IntegerField('Carga Horária Total Prevista', validators=[DataRequired(), NumberRange(min=1)])
        carga_horaria_cumprida = IntegerField('Carga Horária Cumprida', validators=[Optional(), NumberRange(min=0)], default=0)
        ciclo_id = SelectField('Ciclo', coerce=int, validators=[DataRequired()])
        turma_id = SelectField('Turma', coerce=int, validators=[DataRequired()])
        submit = SubmitField('Salvar')

    form = EditDisciplinaForm(obj=disciplina)
    
    ciclos = db.session.scalars(select(Ciclo).where(Ciclo.school_id == school_id).order_by(Ciclo.nome)).all()
    form.ciclo_id.choices = [(c.id, c.nome) for c in ciclos]
    form.turma_id.choices = [(disciplina.turma.id, disciplina.turma.nome)]
    
    if form.validate_on_submit():
        data = {
            'materia': form.materia.data,
            'carga_horaria_prevista': form.carga_horaria_prevista.data,
            'carga_horaria_cumprida': form.carga_horaria_cumprida.data
        }
        DisciplinaService.update_disciplina(disciplina_id, data)
        flash('Disciplina atualizada com sucesso!', 'success')
        return redirect(url_for('disciplina.listar_disciplinas', turma_id=disciplina.turma_id))

    return render_template('editar_disciplina.html', form=form, disciplina=disciplina)

@disciplina_bp.route('/excluir/<int:disciplina_id>', methods=['POST'])
@login_required
@school_admin_or_programmer_required
def excluir_disciplina(disciplina_id):
    form = DeleteForm() # Validação CSRF
    disciplina = db.session.get(Disciplina, disciplina_id)
    school_id = UserService.get_current_school_id()
    
    if disciplina and school_id and disciplina.turma.school_id != school_id:
            flash('Permissão negada.', 'danger')
            return redirect(url_for('disciplina.listar_disciplinas'))
            
    turma_id = disciplina.turma_id if disciplina else None

    if DisciplinaService.delete_disciplina(disciplina_id):
        flash('Disciplina excluída com sucesso.', 'success')
    else:
        flash('Erro ao excluir disciplina.', 'danger')
        
    return redirect(url_for('disciplina.listar_disciplinas', turma_id=turma_id))

@disciplina_bp.route('/api/por-turma/<int:turma_id>')
@login_required
def api_disciplinas_por_turma(turma_id):
    turma = db.session.get(Turma, turma_id)
    if not turma: return jsonify({'error': 'Turma não encontrada'}), 404
    disciplinas = sorted(turma.disciplinas, key=lambda d: d.materia)
    return jsonify([{'id': d.id, 'materia': d.materia} for d in disciplinas])

# --- ROTA DE AUDITORIA E DETALHES ---
@disciplina_bp.route('/detalhes/<int:disciplina_id>')
@login_required
def detalhes_disciplina(disciplina_id):
    disciplina = db.session.get(Disciplina, disciplina_id)
    if not disciplina:
        flash('Disciplina não encontrada.', 'danger')
        return redirect(url_for('disciplina.listar_disciplinas'))
    
    raw_agendamentos = db.session.scalars(
        select(Horario)
        .join(Semana, Horario.semana_id == Semana.id)
        .where(Horario.disciplina_id == disciplina_id)
    ).all()
    
    mapa_dias = {
        'segunda': 0, 'segunda-feira': 0, 'terça': 1, 'terca': 1, 'terça-feira': 1,
        'quarta': 2, 'quarta-feira': 2, 'quinta': 3, 'quinta-feira': 3,
        'sexta': 4, 'sexta-feira': 4, 'sábado': 5, 'sabado': 5, 'domingo': 6
    }

    processed_items = []
    total_tempos_agendados = 0

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

    processed_items.sort(key=lambda x: (x['data_real'], -x['periodo_inicio']), reverse=True)

    grouped_list = []
    if processed_items:
        current_block = processed_items[0]
        for i in range(1, len(processed_items)):
            next_item = processed_items[i]
            if (current_block['data_real'] == next_item['data_real'] and 
                current_block['instrutor_nome'] == next_item['instrutor_nome'] and 
                current_block['periodo_fim'] + 1 == next_item['periodo_inicio']):
                current_block['periodo_fim'] = next_item['periodo_fim']
                current_block['qtd'] += next_item['qtd']
            else:
                grouped_list.append(current_block)
                current_block = next_item
        grouped_list.append(current_block)

    final_output = []
    for item in grouped_list:
        p_str = f"{item['periodo_inicio']}º"
        if item['periodo_inicio'] != item['periodo_fim']:
            p_str = f"{item['periodo_inicio']}º a {item['periodo_fim']}º"
        final_output.append({
            'id': item['id'], 'data': item['data_real'], 'semana': item['semana_nome'],
            'semana_id': item['semana_id'], 'pelotao': item['pelotao'],
            'periodos': p_str, 'qtd': item['qtd'], 'instrutor': item['instrutor_nome']
        })
    
    horas_restantes = disciplina.carga_horaria_prevista - total_tempos_agendados
    
    return render_template('detalhes_disciplina.html', disciplina=disciplina, agendamentos=final_output,
                           total_auditado=total_tempos_agendados, horas_restantes=horas_restantes)