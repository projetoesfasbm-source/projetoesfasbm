# backend/controllers/instrutor_controller.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from wtforms import StringField, SelectField, BooleanField, PasswordField, SubmitField, RadioField
from wtforms.validators import DataRequired, Optional, Email, EqualTo
from flask_wtf import FlaskForm
import json

from ..services.instrutor_service import InstrutorService
from ..services.user_service import UserService
from ..models.user import User
from utils.decorators import (
    admin_or_programmer_required,
    school_admin_or_programmer_required,
    can_view_management_pages_required,
)

instrutor_bp = Blueprint("instrutor", __name__, url_prefix="/instrutor")

posto_graduacao_structured = {
    'Praças': ['Soldado PM', '2º Sargento PM', '1º Sargento PM'],
    'Oficiais': ['1º Tenente PM', 'Capitão PM', 'Major PM', 'Tenente-Coronel PM', 'Coronel PM'],
    'Saúde - Enfermagem': ['Ten Enf', 'Cap Enf', 'Maj Enf', 'Ten Cel Enf', 'Cel Enf'],
    'Saúde - Médicos': ['Ten Med', 'Cap Med', 'Maj Med', 'Ten Cel Med', 'Cel Med'],
    'Outros': ['Civil', 'Outro']
}

class InstrutorForm(FlaskForm):
    nome_completo = StringField("Nome Completo", validators=[DataRequired()])
    nome_de_guerra = StringField("Nome de Guerra", validators=[DataRequired()])
    matricula = StringField("Matrícula", validators=[DataRequired()])
    email = StringField("E-mail", validators=[DataRequired(), Email()])
    password = PasswordField("Senha", validators=[DataRequired(), EqualTo("password2", message="As senhas devem corresponder.")])
    password2 = PasswordField("Confirmar Senha", validators=[DataRequired()])
    
    posto_categoria = SelectField("Categoria", choices=list(posto_graduacao_structured.keys()), validators=[DataRequired()])
    posto_graduacao = SelectField("Posto/Graduação", validators=[DataRequired()])
    posto_graduacao_outro = StringField("Outro (especifique)", validators=[Optional()])

    telefone = StringField("Telefone", validators=[Optional()])
    is_rr = RadioField("Efetivo da Reserva Remunerada (RR)", choices=[(True, 'Sim'), (False, 'Não')], coerce=lambda x: x == 'True', default=False)
    submit = SubmitField("Salvar")


class EditInstrutorForm(FlaskForm):
    nome_completo = StringField("Nome Completo", validators=[DataRequired()])
    nome_de_guerra = StringField("Nome de Guerra", validators=[DataRequired()])
    matricula = StringField("Matrícula", render_kw={"readonly": True})
    email = StringField("E-mail", validators=[DataRequired(), Email()])
    
    posto_categoria = SelectField("Categoria", choices=list(posto_graduacao_structured.keys()), validators=[DataRequired()])
    posto_graduacao = SelectField("Posto/Graduação", validators=[DataRequired()])
    posto_graduacao_outro = StringField("Outro (especifique)", validators=[Optional()])

    telefone = StringField("Telefone", validators=[Optional()] )
    is_rr = RadioField("Efetivo da Reserva Remunerada (RR)", choices=[(True, 'Sim'), (False, 'Não')], coerce=lambda x: x == 'True')
    submit = SubmitField("Salvar Alterações")


class DeleteForm(FlaskForm):
    pass


@instrutor_bp.route("/")
@login_required
@can_view_management_pages_required
def listar_instrutores():
    page = request.args.get('page', 1, type=int)
    search_term = request.args.get('q', None)
    
    instrutores_paginados = InstrutorService.get_all_instrutores(current_user, search_term=search_term, page=page, per_page=15)
    delete_form = DeleteForm()

    return render_template(
        "listar_instrutores.html", 
        instrutores_paginados=instrutores_paginados, 
        delete_form=delete_form,
        search_term=search_term
    )


@instrutor_bp.route("/cadastrar", methods=["GET", "POST"])
@login_required
@school_admin_or_programmer_required
def cadastrar_instrutor():
    form = InstrutorForm()
    
    if form.is_submitted():
         categoria_selecionada = form.posto_categoria.data
         if categoria_selecionada in posto_graduacao_structured:
              form.posto_graduacao.choices = [(p, p) for p in posto_graduacao_structured[categoria_selecionada]]

    if form.validate_on_submit():
        school_id = UserService.get_current_school_id()
        if not school_id:
            flash("Não foi possível identificar a escola para associar o instrutor.", "danger")
            return redirect(url_for("instrutor.listar_instrutores"))

        success, message = InstrutorService.create_full_instrutor(form.data, school_id)
        if success:
            flash(message, "success")
            return redirect(url_for("instrutor.listar_instrutores"))
        else:
            flash(message, "danger")

    return render_template("cadastro_instrutor.html", form=form, postos_data=posto_graduacao_structured)


@instrutor_bp.route("/editar/<int:instrutor_id>", methods=["GET", "POST"])
@login_required
@school_admin_or_programmer_required
def editar_instrutor(instrutor_id):
    instrutor = InstrutorService.get_instrutor_by_id(instrutor_id)
    if not instrutor or not instrutor.user:
        flash("Instrutor não encontrado.", "danger")
        return redirect(url_for("instrutor.listar_instrutores"))

    form = EditInstrutorForm(obj=instrutor)
    
    if request.method == 'GET':
        form.nome_completo.data = instrutor.user.nome_completo
        form.nome_de_guerra.data = instrutor.user.nome_de_guerra
        form.matricula.data = instrutor.user.matricula
        form.email.data = instrutor.user.email
        form.is_rr.data = instrutor.is_rr

        posto_atual = instrutor.user.posto_graduacao
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
    
    if form.is_submitted():
         categoria_selecionada = form.posto_categoria.data
         if categoria_selecionada in posto_graduacao_structured:
              form.posto_graduacao.choices = [(p, p) for p in posto_graduacao_structured[categoria_selecionada]]

    if form.validate_on_submit():
        success, message = InstrutorService.update_instrutor(instrutor_id, form.data)
        if success:
            flash(message, "success")
            return redirect(url_for("instrutor.listar_instrutores"))
        else:
            flash(message, "danger")

    return render_template("editar_instrutor.html", form=form, instrutor=instrutor, postos_data=posto_graduacao_structured)


@instrutor_bp.route("/excluir/<int:instrutor_id>", methods=["POST"])
@login_required
@school_admin_or_programmer_required
def excluir_instrutor(instrutor_id):
    form = DeleteForm()
    if form.validate_on_submit():
        success, message = InstrutorService.delete_instrutor(instrutor_id)
        if success:
            flash(message, "success")
        else:
            flash(message, "danger")
    else:
        flash("Falha na validação do formulário de exclusão.", "danger")
    return redirect(url_for("instrutor.listar_instrutores"))