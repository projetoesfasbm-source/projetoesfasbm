# backend/controllers/aluno_controller.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from sqlalchemy import select, or_
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Optional, Email
import json

from ..models.database import db
from ..services.aluno_service import AlunoService
from ..services.turma_service import TurmaService # <-- IMPORT ADICIONADO
from ..models.user import User
from ..models.aluno import Aluno
from ..models.turma import Turma
from ..models.school import School
from ..models.user_school import UserSchool
from utils.decorators import admin_or_programmer_required, school_admin_or_programmer_required, can_view_management_pages_required

aluno_bp = Blueprint('aluno', __name__, url_prefix='/aluno')

# DICIONÁRIO ESTRUTURADO PARA POSTOS E GRADUAÇÕES
posto_graduacao_structured = {
    'Praças': ['Soldado PM', '2º Sargento PM', '1º Sargento PM'],
    'Oficiais': ['1º Tenente PM', 'Capitão PM', 'Major PM', 'Tenente-Coronel PM', 'Coronel PM'],
    'Saúde - Enfermagem': ['Ten Enf', 'Cap Enf', 'Maj Enf', 'Ten Cel Enf', 'Cel Enf'],
    'Saúde - Médicos': ['Ten Med', 'Cap Med', 'Maj Med', 'Ten Cel Med', 'Cel Med'],
    'Outros': ['Civil', 'Outro']
}

class DeleteForm(FlaskForm):
    pass

def _resolve_school_id_for_user(user: User):
    if user and getattr(user, 'user_schools', None):
        for us in user.user_schools:
            return us.school_id
    return None

def _ensure_school_id_for_current_user(role_required: str = "aluno"):
    sid = _resolve_school_id_for_user(current_user)
    if sid:
        return sid
    sid = session.get('view_as_school_id')
    if sid:
        return int(sid)
    ids = [row[0] for row in db.session.execute(db.select(School.id)).all()]
    if len(ids) == 1:
        only_id = ids[0]
        exists = db.session.execute(
            db.select(UserSchool.id).filter_by(user_id=current_user.id, school_id=only_id)
        ).scalar()
        if not exists:
            from ..services.user_service import UserService
            ok, _ = UserService.assign_school_role(current_user.id, only_id, role_required)
            if not ok:
                db.session.add(UserSchool(user_id=current_user.id, school_id=only_id, role=role_required))
                db.session.commit()
        return only_id
    return None

class EditAlunoForm(FlaskForm):
    nome_completo = StringField('Nome Completo', validators=[DataRequired()])
    email = StringField('E-mail', validators=[DataRequired(), Email()])
    matricula = StringField('Matrícula', render_kw={"readonly": True})
    
    posto_categoria = SelectField("Categoria", choices=list(posto_graduacao_structured.keys()), validators=[DataRequired()])
    posto_graduacao = SelectField('Posto/Graduação', validators=[DataRequired()])
    posto_graduacao_outro = StringField("Outro (especifique)", validators=[Optional()])

    opm = StringField('OPM', validators=[DataRequired()])
    turma_id = SelectField('Turma / Pelotão', coerce=int, validators=[DataRequired()])
    funcao_atual = SelectField('Função Atual', choices=[
        ('', '-- Nenhuma função --'), ('P1', 'P1'), ('P2', 'P2'), ('P3', 'P3'), ('P4', 'P4'), ('P5', 'P5'),
        ('Aux Disc', 'Aux Disc'), ('Aux Cia', 'Aux Cia'), ('Aux Pel', 'Aux Pel'), ('C1', 'C1'), ('C2', 'C2'),
        ('C3', 'C3'), ('C4', 'C4'), ('C5', 'C5'), ('Formatura', 'Formatura'), ('Obras', 'Obras'),
        ('Atletismo', 'Atletismo'), ('Jubileu', 'Jubileu'), ('Dia da Criança', 'Dia da Criança'),
        ('Seminário', 'Seminário'), ('Chefe de Turma', 'Chefe de Turma'), ('Correio', 'Correio'),
        ('Cmt 1° GPM', 'Cmt 1° GPM'), ('Cmt 2° GPM', 'Cmt 2° GPM'), ('Cmt 3° GPM', 'Cmt 3° GPM'),
        ('Socorrista 1', 'Socorrista 1'), ('Socorrista 2', 'Socorrista 2'), ('Motorista 1', 'Motorista 1'),
        ('Motorista 2', 'Motorista 2'), ('Telefonista 1', 'Telefonista 1'), ('Telefonista 2', 'Telefonista 2')
    ], validators=[Optional()])
    submit = SubmitField('Atualizar Perfil')

@aluno_bp.route('/listar')
@login_required
@can_view_management_pages_required
def listar_alunos():
    delete_form = DeleteForm()
    turma_filtrada = request.args.get('turma', None)
    page = request.args.get('page', 1, type=int)
    search_term = request.args.get('q', None)
    
    school_id = _ensure_school_id_for_current_user()
    if not school_id:
        flash('Nenhuma escola associada ou selecionada.', 'danger')
        return redirect(url_for('main.dashboard'))

    alunos_paginados = AlunoService.get_all_alunos(current_user, nome_turma=turma_filtrada, search_term=search_term, page=page, per_page=15)
    
    # --- REFATORADO ---
    # Chamando o serviço em vez de consultar o DB diretamente.
    turmas = TurmaService.get_turmas_by_school(school_id)
    # ------------------
    
    return render_template(
        'listar_alunos.html', 
        alunos_paginados=alunos_paginados, 
        turmas=turmas, 
        turma_filtrada=turma_filtrada, 
        delete_form=delete_form,
        search_term=search_term
    )

@aluno_bp.route('/editar/<int:aluno_id>', methods=['GET', 'POST'])
@login_required
@school_admin_or_programmer_required
def editar_aluno(aluno_id):
    aluno = AlunoService.get_aluno_by_id(aluno_id)
    if not aluno:
        flash("Aluno não encontrado.", 'danger')
        return redirect(url_for('aluno.listar_alunos'))

    school_id = _ensure_school_id_for_current_user()
    if not school_id:
        flash('Nenhuma escola associada ou selecionada.', 'danger')
        return redirect(url_for('aluno.listar_alunos'))

    form = EditAlunoForm(obj=aluno)
    
    # --- REFATORADO ---
    # Chamando o serviço em vez de consultar o DB diretamente.
    turmas = TurmaService.get_turmas_by_school(school_id)
    # ------------------
    
    form.turma_id.choices = [(t.id, t.nome) for t in turmas]

    if request.method == 'GET':
        if aluno.user:
            form.nome_completo.data = aluno.user.nome_completo
            form.email.data = aluno.user.email
            form.matricula.data = aluno.user.matricula
            
            posto_atual = aluno.user.posto_graduacao
            categoria_encontrada = None
            for categoria, postos in posto_graduacao_structured.items():
                if posto_atual in postos:
                    categoria_encontrada = categoria
                    break
            
            if categoria_encontrada:
                form.posto_categoria.data = categoria_encontrada
                form.posto_graduacao.choices = [(p, p) for p in posto_graduacao_structured[categoria_encontrada]]
                form.posto_graduacao.data = posto_atual
            elif posto_atual:
                form.posto_categoria.data = 'Outros'
                form.posto_graduacao.choices = [(p, p) for p in posto_graduacao_structured['Outros']]
                form.posto_graduacao.data = 'Outro'
                form.posto_graduacao_outro.data = posto_atual
                
        form.opm.data = aluno.opm
        form.turma_id.data = aluno.turma_id
    
    if form.is_submitted() and 'funcao_atual' not in request.form:
         categoria_selecionada = form.posto_categoria.data
         if categoria_selecionada in posto_graduacao_structured:
             form.posto_graduacao.choices = [(p, p) for p in posto_graduacao_structured[categoria_selecionada]]

    if form.validate_on_submit() and 'funcao_atual' not in request.form:
        success, message = AlunoService.update_aluno(aluno_id, form.data)
        if success:
            flash(message, 'success')
            return redirect(url_for('aluno.listar_alunos'))
        else:
            flash(message, 'error')

    return render_template('editar_aluno.html', aluno=aluno, form=form, postos_data=posto_graduacao_structured)

@aluno_bp.route('/editar/<int:aluno_id>/funcao', methods=['POST'])
@login_required
@school_admin_or_programmer_required
def editar_funcao_aluno(aluno_id):
    success, message = AlunoService.update_funcao_aluno(aluno_id, request.form)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('aluno.editar_aluno', aluno_id=aluno_id))


@aluno_bp.route('/excluir/<int:aluno_id>', methods=['POST'])
@login_required
@school_admin_or_programmer_required
def excluir_aluno(aluno_id):
    form = DeleteForm()
    if form.validate_on_submit():
        success, message = AlunoService.delete_aluno(aluno_id)
        if success:
            flash(message, 'success')
        else:
            flash(message, 'danger')
    else:
        flash('Falha na validação do token CSRF.', 'danger')
    return redirect(url_for('aluno.listar_alunos'))