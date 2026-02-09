from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from sqlalchemy import select
from wtforms import StringField, TextAreaField, DateTimeLocalField, SubmitField, SelectField
from wtforms.validators import DataRequired

from ..models.database import db
from ..models.historico_disciplina import HistoricoDisciplina
from ..models.disciplina import Disciplina
from ..models.turma import Turma
from ..models.elogio import Elogio  # <--- IMPORTAÇÃO ADICIONADA
from ..services.historico_service import HistoricoService
from ..services.aluno_service import AlunoService
from utils.decorators import admin_or_programmer_required, aluno_profile_required, can_view_management_pages_required

historico_bp = Blueprint('historico', __name__, url_prefix='/historico')

@historico_bp.route('/')
@login_required
@aluno_profile_required
def index():
    """Página principal de seleção do 'Meu CTSP'."""
    return render_template('meu_ctsp_index.html')

@historico_bp.route('/sancoes')
@login_required
@aluno_profile_required
def sancoes():
    """Página para visualizar sanções (placeholder)."""
    return render_template('sancoes.html')

@historico_bp.route('/elogios')
@login_required
@aluno_profile_required
def elogios():
    """Página para visualizar elogios (placeholder)."""
    return render_template('elogios.html')

@historico_bp.route('/funcional/<int:aluno_id>')
@login_required
@aluno_profile_required
def historico_funcional(aluno_id):
    """Página para visualizar o histórico unificado do aluno."""
    aluno = AlunoService.get_aluno_by_id(aluno_id)
    if not aluno:
        flash("Aluno não encontrado.", "danger")
        return redirect(url_for('main.dashboard'))
    
    if current_user.role == 'aluno' and current_user.aluno_profile.id != aluno_id:
        flash("Você não tem permissão para ver o histórico de outro aluno.", "danger")
        return redirect(url_for('main.dashboard'))

    historico_unificado = HistoricoService.get_unified_historico_for_aluno(aluno_id)
    
    # --- ADIÇÃO: Buscar Elogios para o Histórico Funcional ---
    elogios_lista = Elogio.query.filter_by(aluno_id=aluno.id).all()

    return render_template('historico_funcional.html', 
                           aluno=aluno, 
                           historico=historico_unificado,
                           elogios=elogios_lista) # <--- PASSANDO A VARIÁVEL


@historico_bp.route('/minhas-notas')
@login_required
@aluno_profile_required
def minhas_notas():
    aluno_id = current_user.aluno_profile.id
    aluno = AlunoService.get_aluno_by_id(aluno_id)
    if not aluno:
        flash("Aluno não encontrado.", 'danger')
        return redirect(url_for('main.dashboard'))

    if aluno.turma and aluno.turma.school:
        school_id = aluno.turma.school.id
        
        # Filtra disciplinas da escola correta
        disciplinas_da_escola = db.session.scalars(
            select(Disciplina).join(Turma).where(Turma.school_id == school_id)
        ).all()

        matriculas_existentes_ids = {h.disciplina_id for h in aluno.historico_disciplinas}
        
        novas_matriculas = False
        for disciplina in disciplinas_da_escola:
            if disciplina.turma_id == aluno.turma_id and disciplina.id not in matriculas_existentes_ids:
                nova_matricula = HistoricoDisciplina(aluno_id=aluno.id, disciplina_id=disciplina.id)
                db.session.add(nova_matricula)
                novas_matriculas = True
        
        if novas_matriculas:
            db.session.commit()

    historico_disciplinas = HistoricoService.get_historico_disciplinas_for_aluno(aluno_id)
    notas_finais = [h.nota for h in historico_disciplinas if h.nota is not None]
    media_final_curso = sum(notas_finais) / len(notas_finais) if notas_finais else 0.0

    # --- ADIÇÃO: Buscar Elogios para o Boletim ---
    elogios_lista = Elogio.query.filter_by(aluno_id=aluno.id).all()

    return render_template('historico_aluno.html',
                           aluno=aluno,
                           historico_disciplinas=historico_disciplinas,
                           media_final_curso=media_final_curso,
                           elogios=elogios_lista,  # <--- PASSANDO A VARIÁVEL
                           is_own_profile=True)

@historico_bp.route('/ver/<int:aluno_id>')
@login_required
@can_view_management_pages_required
def ver_historico_aluno(aluno_id):
    if current_user.role not in ['super_admin', 'programador', 'admin_escola']:
        flash("Você não tem permissão para visualizar este histórico.", 'danger')
        return redirect(url_for('main.dashboard'))

    aluno = AlunoService.get_aluno_by_id(aluno_id)
    if not aluno:
        flash("Aluno não encontrado.", 'danger')
        return redirect(url_for('aluno.listar_alunos'))

    historico_disciplinas = HistoricoService.get_historico_disciplinas_for_aluno(aluno_id)
    notas_finais = [h.nota for h in historico_disciplinas if h.nota is not None]
    media_final_curso = sum(notas_finais) / len(notas_finais) if notas_finais else 0.0

    # --- ADIÇÃO: Buscar Elogios para visualização do Admin ---
    elogios_lista = Elogio.query.filter_by(aluno_id=aluno.id).all()

    return render_template('historico_aluno.html',
                           aluno=aluno,
                           historico_disciplinas=historico_disciplinas,
                           media_final_curso=media_final_curso,
                           elogios=elogios_lista,  # <--- PASSANDO A VARIÁVEL
                           is_own_profile=False)


@historico_bp.route('/avaliar/<int:historico_id>', methods=['POST'])
@login_required
def avaliar_aluno_disciplina(historico_id):
    registro = db.session.get(HistoricoDisciplina, historico_id)
    if not registro:
        flash("Registro de avaliação não encontrado.", 'danger')
        return redirect(url_for('main.dashboard'))

    is_own_profile = hasattr(current_user, 'aluno_profile') and current_user.aluno_profile.id == registro.aluno_id
    is_admin = getattr(current_user, 'role', None) in ['super_admin', 'programador', 'admin_escola']

    if not (is_own_profile or is_admin):
        flash("Você não tem permissão para realizar esta ação.", 'danger')
        return redirect(url_for('main.dashboard'))

    form_data = request.form.to_dict()
    success, message, aluno_id = HistoricoService.avaliar_aluno(historico_id, form_data, from_admin=is_admin)

    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')

    if is_admin:
        return redirect(url_for('historico.ver_historico_aluno', aluno_id=aluno_id))
    return redirect(url_for('historico.minhas_notas'))