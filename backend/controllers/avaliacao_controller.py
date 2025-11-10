# backend/controllers/avaliacao_controller.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from flask_login import login_required, current_user
from sqlalchemy import select
from datetime import datetime, timedelta

from ..models.database import db
from ..models.aluno import Aluno
from ..models.turma import Turma
from ..models.user import User
from ..services.avaliacao_service import AvaliacaoService
from utils.decorators import admin_or_programmer_required

avaliacao_bp = Blueprint('avaliacao', __name__, url_prefix='/avaliacao')

@avaliacao_bp.before_request
def check_eligibility():
    """Verifica se a escola ativa é elegível para avaliação atitudinal antes de qualquer requisição."""
    active_school = g.get('active_school')
    if not active_school:
        flash('Nenhuma escola ativa selecionada.', 'warning')
        return redirect(url_for('main.dashboard'))
    
    # BLOQUEIO: Se for CTSP (código 'cfs'), impede o acesso.
    if active_school.npccal_type == 'cfs':
        flash('O módulo de Avaliação Atitudinal não está disponível para cursos CTSP.', 'info')
        return redirect(url_for('main.dashboard'))

@avaliacao_bp.route('/')
@login_required
@admin_or_programmer_required
def index():
    active_school = g.get('active_school')
    turmas = db.session.scalars(
        select(Turma).where(Turma.school_id == active_school.id).order_by(Turma.nome)
    ).all()
    
    turma_id = request.args.get('turma_id', type=int)
    alunos = []
    if turma_id:
        alunos = db.session.scalars(
            select(Aluno).join(User).where(Aluno.turma_id == turma_id).order_by(User.nome_completo)
        ).all()

    return render_template('avaliacao/index.html', turmas=turmas, alunos=alunos, selected_turma_id=turma_id)

@avaliacao_bp.route('/nova/<int:aluno_id>', methods=['GET', 'POST'])
@login_required
@admin_or_programmer_required
def nova_avaliacao(aluno_id):
    aluno = db.session.get(Aluno, aluno_id)
    if not aluno: return redirect(url_for('avaliacao.index'))

    if request.method == 'POST':
        success, msg = AvaliacaoService.criar_avaliacao(request.form, current_user.id)
        flash(msg, 'success' if success else 'danger')
        if success: return redirect(url_for('avaliacao.ver_avaliacoes', aluno_id=aluno.id))

    data_fim = datetime.now().strftime('%Y-%m-%d')
    data_inicio = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

    return render_template('avaliacao/nova.html', aluno=aluno, 
                         criterios=AvaliacaoService.CRITERIOS_FADA,
                         data_inicio=data_inicio, data_fim=data_fim)

@avaliacao_bp.route('/aluno/<int:aluno_id>')
@login_required
def ver_avaliacoes(aluno_id):
    if current_user.role == 'aluno' and current_user.aluno_profile.id != aluno_id:
         flash('Acesso negado.', 'danger')
         return redirect(url_for('main.dashboard'))
    aluno = db.session.get(Aluno, aluno_id)
    return render_template('avaliacao/ver.html', aluno=aluno, 
                         avaliacoes=AvaliacaoService.get_avaliacoes_aluno(aluno_id))

@avaliacao_bp.route('/detalhe/<int:avaliacao_id>')
@login_required
def detalhe_avaliacao(avaliacao_id):
    av = AvaliacaoService.get_avaliacao_por_id(avaliacao_id)
    if not av: return redirect(url_for('main.dashboard'))
    if current_user.role == 'aluno' and current_user.aluno_profile.id != av.aluno_id:
         return redirect(url_for('main.dashboard'))
    return render_template('avaliacao/detalhe.html', avaliacao=av)