# backend/controllers/user_controller.py
from __future__ import annotations

import os
import re
import secrets
from datetime import datetime
from typing import Optional
import json

from flask import (
    Blueprint, current_app, flash, redirect, render_template,
    request, url_for, jsonify, abort
)
from flask_login import current_user, login_required
from sqlalchemy import text, select, case
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, RadioField
from wtforms.validators import DataRequired, Email, EqualTo, Optional as WTFormsOptional, ValidationError
from flask_wtf.file import FileField, FileAllowed

from backend.models.database import db
from backend.services.aluno_service import AlunoService
from backend.services.instrutor_service import InstrutorService
from backend.models.user import User
from backend.models.turma import Turma
from backend.models.school import School
from backend.models.user_school import UserSchool
from backend.services.user_service import UserService
from utils.decorators import super_admin_required, admin_required

user_bp = Blueprint("user", __name__, url_prefix="/user")

posto_graduacao_structured = {
    'Praças': ['Soldado PM', '2º Sargento PM', '1º Sargento PM'],
    'Oficiais': ['Aluno Oficial', '1º Tenente PM', 'Capitão PM', 'Major PM', 'Tenente-Coronel PM', 'Coronel PM'],
    'Saúde - Enfermagem': ['Ten Enf', 'Cap Enf', 'Maj Enf', 'Ten Cel Enf', 'Cel Enf'],
    'Saúde - Médicos': ['Ten Med', 'Cap Med', 'Maj Med', 'Ten Cel Med', 'Cel Med'],
    'Outros': ['Civil', 'Outro']
}

class MeuPerfilForm(FlaskForm):
    nome_completo = StringField('Nome Completo', validators=[DataRequired()])
    email = StringField('E-mail', validators=[DataRequired(), Email()])
    posto_categoria = SelectField("Categoria", choices=list(posto_graduacao_structured.keys()), validators=[DataRequired()])
    posto_graduacao = SelectField('Posto/Graduação', choices=[], validators=[DataRequired()])
    turma_id = SelectField('Turma', coerce=int, validators=[WTFormsOptional()])
    is_rr = RadioField("Efetivo da Reserva Remunerada (RR)", choices=[('True', 'Sim'), ('False', 'Não')], coerce=lambda x: x == 'True', default=False)

    # Aceita arquivos, sem limite manual de tamanho aqui (o Service vai comprimir)
    foto_perfil = FileField('Alterar Foto de Perfil', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'], 'Apenas imagens!')
    ])

    current_password = PasswordField('Senha Atual', validators=[WTFormsOptional()])
    new_password = PasswordField('Nova Senha', validators=[WTFormsOptional(), EqualTo('confirm_new_password', message='As senhas não correspondem.')])
    confirm_new_password = PasswordField('Confirmar Nova Senha', validators=[WTFormsOptional()])
    submit = SubmitField('Salvar Alterações')

def norm_email(v: Optional[str]) -> Optional[str]:
    return v.strip().lower() if v else None

def norm_idfunc(v: Optional[str]) -> Optional[str]:
    if not v: return None
    return re.sub(r"\D+", "", v.strip()) or None

def set_password_hash_on_user(user_obj, plain: str):
    if hasattr(user_obj, "set_password") and callable(getattr(user_obj, "set_password")):
        user_obj.set_password(plain)
    else:
        user_obj.password_hash = generate_password_hash(plain)

def exists_in_users_by(column: str, value: str) -> bool:
    return db.session.scalar(select(User).where(getattr(User, column) == value, User.id != current_user.id)) is not None

def generate_unique_username(base: str, max_tries: int = 50) -> str:
    base = re.sub(r"[^a-z0-9._-]+", "-", base.lower())
    candidate = base or "user"
    if not exists_in_users_by("username", candidate): return candidate
    for i in range(1, max_tries + 1):
        candidate = f"{base}-{i}"
        if not exists_in_users_by("username", candidate): return candidate
    suffix = secrets.token_hex(2)
    candidate = f"{base}-{suffix}"
    return candidate

@user_bp.route("/meu-perfil", methods=["GET", "POST"])
@login_required
def meu_perfil():
    form = MeuPerfilForm(obj=current_user)
    form.turma_id.choices = []

    if request.method == 'GET':
        posto_atual = current_user.posto_graduacao
        categoria_encontrada = 'Outros'
        for categoria, postos in posto_graduacao_structured.items():
            if posto_atual in postos:
                categoria_encontrada = categoria
                break
        form.posto_categoria.data = categoria_encontrada

    categoria_selecionada = form.posto_categoria.data or 'Praças'
    form.posto_graduacao.choices = [(p, p) for p in posto_graduacao_structured.get(categoria_selecionada, [])]
    if request.method == 'GET':
        form.posto_graduacao.data = current_user.posto_graduacao

    if current_user.role == 'aluno' and current_user.aluno_profile:
        school_id = current_user.aluno_profile.turma.school_id if current_user.aluno_profile.turma else None
        if school_id:
            turmas = db.session.scalars(select(Turma).filter_by(school_id=school_id).order_by(Turma.nome)).all()
            form.turma_id.choices = [(t.id, t.nome) for t in turmas]
            if request.method == 'GET':
                 form.turma_id.data = current_user.aluno_profile.turma_id
    elif current_user.role == 'instrutor' and hasattr(current_user, 'instrutor_profile') and current_user.instrutor_profile:
        if request.method == 'GET':
            form.is_rr.data = current_user.instrutor_profile.is_rr

    if form.validate_on_submit():
        try:
            current_user.nome_completo = form.nome_completo.data
            current_user.posto_graduacao = form.posto_graduacao.data
            nome_de_guerra = request.form.get('nome_de_guerra')
            if nome_de_guerra: current_user.nome_de_guerra = nome_de_guerra

            if form.email.data != current_user.email and exists_in_users_by("email", form.email.data):
                flash("Este e-mail já está em uso por outro usuário.", "warning")
            else:
                current_user.email = form.email.data

            if form.new_password.data:
                if not current_user.check_password(form.current_password.data):
                    flash("A senha atual está incorreta.", "danger")
                else:
                    set_password_hash_on_user(current_user, form.new_password.data)
                    current_user.must_change_password = False
                    flash("Senha alterada com sucesso.", "success")

            if current_user.role == 'aluno' and current_user.aluno_profile:
                current_user.aluno_profile.turma_id = form.turma_id.data
                if form.foto_perfil.data:
                    # O serviço agora cuida da compressão
                    success, message = AlunoService.update_profile_picture(current_user.aluno_profile.id, form.foto_perfil.data)
                    flash(message, 'success' if success else 'danger')

            if current_user.role == 'instrutor' and hasattr(current_user, 'instrutor_profile') and current_user.instrutor_profile:
                current_user.instrutor_profile.is_rr = form.is_rr.data
                if form.foto_perfil.data:
                    # O serviço agora cuida da compressão
                    success, message = InstrutorService.update_profile_picture(current_user.instrutor_profile.id, form.foto_perfil.data)
                    flash(message, 'success' if success else 'danger')

            db.session.commit()
            flash("Perfil atualizado com sucesso.", "success")
            return redirect(url_for("user.meu_perfil"))
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Erro ao salvar Meu Perfil: {e}")
            flash("Ocorreu um erro ao salvar seu perfil.", "danger")

    return render_template("meu_perfil.html", user=current_user, form=form, postos_data=posto_graduacao_structured)

# ... (restante do arquivo inalterado) ...
@user_bp.route("/change-password-ajax", methods=["POST"])
@login_required
def change_password_ajax():
    data = request.json
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    confirm_new_password = data.get('confirm_new_password')

    if not all([current_password, new_password, confirm_new_password]):
        return jsonify({'success': False, 'message': 'Todos os campos são obrigatórios.'}), 400
    if not current_user.check_password(current_password):
        return jsonify({'success': False, 'message': 'A senha atual está incorreta.'}), 400
    if new_password != confirm_new_password:
        return jsonify({'success': False, 'message': 'As novas senhas não correspondem.'}), 400
    if len(new_password) < 8:
        return jsonify({'success': False, 'message': 'A nova senha deve ter pelo menos 8 caracteres.'}), 400

    try:
        set_password_hash_on_user(current_user, new_password)
        current_user.must_change_password = False
        db.session.commit()
        return jsonify({'success': True, 'message': 'Senha alterada com sucesso!'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao alterar senha via AJAX: {e}")
        return jsonify({'success': False, 'message': 'Ocorreu um erro interno ao alterar a senha.'}), 500

@user_bp.route("/criar-admin", methods=["GET", "POST"])
@login_required
def criar_admin_escola():
    school_id = UserService.get_current_school_id()
    if not (current_user.is_programador or current_user.is_admin_escola_in_school(school_id)):
        flash("Você não tem permissão para criar administradores.", "danger")
        return redirect(url_for("main.dashboard"))

    if not school_id:
        flash("Selecione uma escola primeiro.", "danger")
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        try:
            nome = (request.form.get("nome") or "").strip()
            email = norm_email(request.form.get("email"))
            id_func = norm_idfunc(request.form.get("id_func"))

            if not all([nome, email, id_func]):
                 flash("Todos os campos são obrigatórios.", "warning")
                 return redirect(url_for("user.criar_admin_escola"))

            base_username = (email.split("@")[0] if "@" in email else email)
            username = generate_unique_username(base_username)

            if db.session.scalar(select(User).where(User.email == email)):
                flash("E-mail já está em uso.", "warning")
                return redirect(url_for("user.criar_admin_escola"))
            if db.session.scalar(select(User).where(User.matricula == id_func)):
                flash("Matrícula (ID Func) já está em uso.", "warning")
                return redirect(url_for("user.criar_admin_escola"))

            temp_pass = secrets.token_urlsafe(8)

            user = User(
                matricula=id_func,
                username=username,
                email=email,
                nome_completo=nome,
                role="aluno",
                is_active=True,
                must_change_password=True
            )
            set_password_hash_on_user(user, temp_pass)

            db.session.add(user)
            db.session.flush()

            UserService.set_user_role_for_school(user.id, school_id, "admin_escola")
            db.session.commit()

            flash(f"Administrador criado com sucesso. Username: {username} • Senha temporária: {temp_pass}", "success")
            return redirect(url_for("user.listar_admins_escola"))

        except IntegrityError as ie:
            db.session.rollback()
            msg = str(getattr(ie, "orig", ie))
            flash(f"Erro de integridade: {msg}", "danger")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao criar administrador")
            flash("Ocorreu um erro ao criar o administrador.", "danger")

    return render_template("criar_admin_escola.html")

@user_bp.route("/admins", methods=["GET"])
@login_required
@admin_required
def listar_admins_escola():
    school_id = UserService.get_current_school_id()
    if not school_id:
        flash("Selecione uma escola para gerenciar usuários.", "warning")
        return redirect(url_for('main.dashboard'))

    role_priority = case(
        (UserSchool.role == 'admin_escola', 1),
        (UserSchool.role == 'admin_sens', 2),
        (UserSchool.role == 'admin_cal', 2),
        (UserSchool.role == 'instrutor', 3),
        else_=4
    )

    results = db.session.execute(
        select(User, UserSchool)
        .join(UserSchool)
        .where(UserSchool.school_id == school_id)
        .order_by(role_priority, User.nome_completo)
    ).all()

    return render_template("listar_admins_escola.html", usuarios_com_role=results)


@user_bp.route("/alterar-papel/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def alterar_papel_usuario(user_id):
    school_id = UserService.get_current_school_id()
    if not school_id:
        return redirect(url_for('main.dashboard'))

    user = db.session.get(User, user_id)
    if not user:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for('user.listar_admins_escola'))

    if user.id == current_user.id:
        flash("Você não pode alterar seu próprio papel por aqui.", "warning")
        return redirect(url_for('user.listar_admins_escola'))

    if user.role == 'programador':
        flash("Não é permitido alterar o papel de um Programador.", "danger")
        return redirect(url_for('user.listar_admins_escola'))

    novo_role = request.form.get('novo_role')
    papeis_validos = ['admin_cal', 'admin_sens', 'admin_escola', 'instrutor', 'aluno']

    if novo_role not in papeis_validos:
        flash("Papel inválido selecionado.", "danger")
        return redirect(url_for('user.listar_admins_escola'))

    success, msg = UserService.set_user_role_for_school(user.id, school_id, novo_role)

    if success:
        flash(f"Permissões de {user.nome_completo} atualizadas para: {novo_role.upper()}", "success")
    else:
        flash(msg, "danger")

    return redirect(url_for('user.listar_admins_escola'))