from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from sqlalchemy import select, or_
from sqlalchemy.orm import joinedload
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Optional, Email
import json

from ..models.database import db
from ..services.aluno_service import AlunoService
from ..services.turma_service import TurmaService
from ..models.user import User
from ..models.aluno import Aluno
from ..models.turma import Turma
from ..models.school import School
from ..models.user_school import UserSchool
from ..services.user_service import UserService # Importante para resolver escola
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

    # 1. Garante ID da Escola
    school_id = session.get('active_school_id') or UserService.get_current_school_id()
    if not school_id:
        flash('Nenhuma escola associada ou selecionada.', 'danger')
        return redirect(url_for('main.dashboard'))

    # 2. QUERY BLINDADA (Substitui AlunoService.get_all_alunos para garantir visibilidade)
    # Explicação: Fazemos JOIN com UserSchool para garantir que o aluno pertence à escola.
    # Usamos LEFT JOIN com Turma para que alunos "sem turma" não sumam da lista.

    query = db.session.query(Aluno).join(User).join(UserSchool).outerjoin(Turma).options(
        joinedload(Aluno.turma),
        joinedload(Aluno.user)
    ).filter(
        UserSchool.school_id == school_id,
        UserSchool.role == 'aluno'
    )

    # Filtros
    if search_term:
        term = f"%{search_term}%"
        query = query.filter(
            or_(
                User.nome_completo.like(term),
                User.matricula.like(term),
                User.nome_de_guerra.like(term)
            )
        )

    if turma_filtrada:
        # Se o filtro for numérico (ID), filtra por ID. Se for texto, tenta filtrar por nome.
        if turma_filtrada.isdigit():
             query = query.filter(Aluno.turma_id == int(turma_filtrada))
        else:
             query = query.filter(Turma.nome == turma_filtrada)

    # Paginação
    alunos_paginados = query.order_by(User.nome_completo).paginate(page=page, per_page=15, error_out=False)

    # Carrega turmas para o filtro
    turmas = TurmaService.get_turmas_by_school(school_id)

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
    school_id = session.get('active_school_id') or UserService.get_current_school_id()
    if not school_id:
        flash('Nenhuma escola associada.', 'danger')
        return redirect(url_for('aluno.listar_alunos'))

    # Busca segura garantindo escola
    aluno = db.session.query(Aluno).join(User).join(UserSchool).filter(
        Aluno.id == aluno_id,
        UserSchool.school_id == school_id
    ).first()

    if not aluno:
        flash("Aluno não encontrado nesta escola.", 'danger')
        return redirect(url_for('aluno.listar_alunos'))

    form = EditAlunoForm(obj=aluno)

    # Carrega turmas apenas da escola atual
    turmas = TurmaService.get_turmas_by_school(school_id)
    # Adiciona opção "Sem Turma"
    turma_choices = [(0, '-- Selecione --')] + [(t.id, t.nome) for t in turmas]
    form.turma_id.choices = turma_choices

    if request.method == 'GET':
        if aluno.user:
            form.nome_completo.data = aluno.user.nome_completo
            form.email.data = aluno.user.email
            form.matricula.data = aluno.user.matricula

            # Lógica de Posto/Graduação
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
        form.turma_id.data = aluno.turma_id if aluno.turma_id else 0

    # Atualização dinâmica de choices no POST
    if form.is_submitted():
         categoria_selecionada = form.posto_categoria.data
         if categoria_selecionada in posto_graduacao_structured:
             form.posto_graduacao.choices = [(p, p) for p in posto_graduacao_structured[categoria_selecionada]]

    if form.validate_on_submit():
        # Lógica de Salvamento Manual para garantir controle
        try:
            # User Info
            aluno.user.nome_completo = form.nome_completo.data
            aluno.user.email = form.email.data

            # Posto
            cat = form.posto_categoria.data
            grad = form.posto_graduacao.data
            if cat == 'Outros' and grad == 'Outro':
                aluno.user.posto_graduacao = form.posto_graduacao_outro.data
            else:
                aluno.user.posto_graduacao = grad

            # Aluno Info
            aluno.opm = form.opm.data
            t_id = form.turma_id.data
            aluno.turma_id = t_id if t_id and t_id != 0 else None

            if form.funcao_atual.data:
                 # Se houver lógica específica para função, implemente aqui ou chame service
                 pass

            db.session.commit()
            flash('Aluno atualizado com sucesso!', 'success')
            return redirect(url_for('aluno.listar_alunos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar: {str(e)}', 'danger')

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
        # Remove apenas o vínculo da escola atual para segurança
        school_id = session.get('active_school_id') or UserService.get_current_school_id()
        if not school_id:
             flash('Erro de escola.', 'danger')
             return redirect(url_for('aluno.listar_alunos'))

        try:
            aluno = db.session.query(Aluno).join(UserSchool).filter(
                Aluno.id == aluno_id,
                UserSchool.school_id == school_id
            ).first()

            if aluno:
                # Remove Aluno Profile
                db.session.delete(aluno)
                # Remove Vínculo UserSchool
                db.session.query(UserSchool).filter_by(user_id=aluno.user_id, school_id=school_id).delete()
                db.session.commit()
                flash('Aluno removido da escola.', 'success')
            else:
                flash('Aluno não encontrado.', 'danger')

        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao excluir: {str(e)}', 'danger')
    else:
        flash('Falha CSRF.', 'danger')
    return redirect(url_for('aluno.listar_alunos'))