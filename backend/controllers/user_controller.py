# backend/controllers/user_controller.py
from __future__ import annotations

import os
import re
import secrets
from datetime import datetime
from typing import Optional
import json

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
    jsonify
)
from flask_login import current_user, login_required
from sqlalchemy import text, select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, RadioField
from wtforms.validators import DataRequired, Email, EqualTo, Optional
from flask_wtf.file import FileField, FileAllowed

from ..models.database import db
from ..services.aluno_service import AlunoService
from ..services.instrutor_service import InstrutorService
from ..models.user import User
from ..models.turma import Turma
from ..models.school import School
from ..models.user_school import UserSchool

user_bp = Blueprint("user", __name__, url_prefix="/user")

# DICIONÁRIO ESTRUTURADO PARA POSTOS E GRADUAÇÕES
posto_graduacao_structured = {
    'Praças': ['Soldado PM', '2º Sargento PM', '1º Sargento PM'],
    'Oficiais': ['1º Tenente PM', 'Capitão PM', 'Major PM', 'Tenente-Coronel PM', 'Coronel PM'],
    'Saúde - Enfermagem': ['Ten Enf', 'Cap Enf', 'Maj Enf', 'Ten Cel Enf', 'Cel Enf'],
    'Saúde - Médicos': ['Ten Med', 'Cap Med', 'Maj Med', 'Ten Cel Med', 'Cel Med'],
    'Outros': ['Civil', 'Outro']
}

# ===== Forms =====
class MeuPerfilForm(FlaskForm):
    nome_completo = StringField('Nome Completo', validators=[DataRequired()])
    email = StringField('E-mail', validators=[DataRequired(), Email()])
    
    posto_categoria = SelectField("Categoria", choices=list(posto_graduacao_structured.keys()), validators=[DataRequired()])
    posto_graduacao = SelectField('Posto/Graduação', choices=[], validators=[DataRequired()]) # Choices são dinâmicas

    turma_id = SelectField('Turma', coerce=int, validators=[Optional()])
    is_rr = RadioField("Efetivo da Reserva Remunerada (RR)", choices=[('True', 'Sim'), ('False', 'Não')], coerce=lambda x: x == 'True', default=False)
    
    foto_perfil = FileField('Alterar Foto de Perfil', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'], 'Apenas imagens!')])

    current_password = PasswordField('Senha Atual', validators=[Optional()])
    new_password = PasswordField('Nova Senha', validators=[Optional(), EqualTo('confirm_new_password', message='As senhas não correspondem.')])
    confirm_new_password = PasswordField('Confirmar Nova Senha', validators=[Optional()])
    submit = SubmitField('Salvar Alterações')


# ===== Utils =====
def norm_email(v: Optional[str]) -> Optional[str]:
    return v.strip().lower() if v else None

def norm_idfunc(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    return re.sub(r"\D+", "", v.strip()) or None

def set_password_hash_on_user(user_obj, plain: str):
    if hasattr(user_obj, "set_password") and callable(getattr(user_obj, "set_password")):
        user_obj.set_password(plain)
    else:
        user_obj.password_hash = generate_password_hash(plain)

def exists_in_users_by(column: str, value: str) -> bool:
    # Ignora o usuário atual na verificação para permitir que ele salve seu próprio perfil
    return db.session.scalar(select(User).where(getattr(User, column) == value, User.id != current_user.id)) is not None

def generate_unique_username(base: str, max_tries: int = 50) -> str:
    base = re.sub(r"[^a-z0-9._-]+", "-", base.lower())
    candidate = base or "user"
    if not exists_in_users_by("username", candidate):
        return candidate
    for i in range(1, max_tries + 1):
        candidate = f"{base}-{i}"
        if not exists_in_users_by("username", candidate):
            return candidate
    suffix = secrets.token_hex(2)
    candidate = f"{base}-{suffix}"
    return candidate

def insert_user_school(user_id: int, school_id: int, role: str):
    us = UserSchool(user_id=user_id, school_id=school_id, role=role, created_at=datetime.utcnow())
    db.session.add(us)

# ===== Rota Meu Perfil =====
@user_bp.route("/meu-perfil", methods=["GET", "POST"])
@login_required
def meu_perfil():
    form = MeuPerfilForm(obj=current_user)
    
    # --- CORREÇÃO APLICADA AQUI ---
    # Garante que a lista de turmas seja sempre uma lista, mesmo que vazia,
    # para evitar o erro em perfis que não são de alunos.
    form.turma_id.choices = []
    
    # Lógica para popular dinamicamente as escolhas de Posto/Graduação
    if request.method == 'GET':
        posto_atual = current_user.posto_graduacao
        categoria_encontrada = 'Outros' # Padrão
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
            
            # --- Adicionado para salvar o nome de guerra ---
            nome_de_guerra = request.form.get('nome_de_guerra')
            if nome_de_guerra:
                current_user.nome_de_guerra = nome_de_guerra
            
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
                    success, message = AlunoService.update_profile_picture(current_user.aluno_profile.id, form.foto_perfil.data)
                    flash(message, 'success' if success else 'danger')

            if current_user.role == 'instrutor' and hasattr(current_user, 'instrutor_profile') and current_user.instrutor_profile:
                current_user.instrutor_profile.is_rr = form.is_rr.data
                if form.foto_perfil.data:
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


# ===== Rotas de Admin (sem alterações, mantidas como estavam) =====
@user_bp.route("/criar-admin", methods=["GET", "POST"])
@login_required
def criar_admin_escola():
    role_atual = getattr(current_user, "role", None)
    if role_atual not in ("admin_escola", "super_admin", "programador"):
        flash("Você não tem permissão para criar administradores.", "danger")
        return redirect(url_for("main.dashboard"))

    escola_id = None
    if hasattr(current_user, 'user_schools') and current_user.user_schools:
        escola_id = current_user.user_schools[0].school_id

    if not escola_id:
        flash("Não foi possível identificar a escola do usuário atual.", "danger")
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
                flash("E-mail já está em uso na tabela de usuários.", "warning")
                return redirect(url_for("user.criar_admin_escola"))
            if db.session.scalar(select(User).where(User.matricula == id_func)):
                flash("Matrícula (ID Func) já está em uso na tabela de usuários.", "warning")
                return redirect(url_for("user.criar_admin_escola"))

            temp_pass = secrets.token_urlsafe(8)
            
            user = User(
                matricula=id_func,
                username=username,
                email=email,
                nome_completo=nome,
                role="admin_escola",
                is_active=True,
                must_change_password=True
            )
            set_password_hash_on_user(user, temp_pass)

            db.session.add(user)
            db.session.flush()
            insert_user_school(user.id, escola_id, "admin_escola")
            db.session.commit()

            flash(f"Administrador criado com sucesso. Username: {username} • Senha temporária: {temp_pass}", "success")
            return redirect(url_for("user.lista_admins_escola"))

        except IntegrityError as ie:
            db.session.rollback()
            msg = str(getattr(ie, "orig", ie))
            if "email" in msg.lower():
                flash("Conflito: e-mail já cadastrado.", "danger")
            elif "matricula" in msg.lower():
                flash("Conflito: Matrícula (ID Func) já cadastrada.", "danger")
            else:
                flash(f"Não foi possível criar (Erro de Integridade). Detalhe: {msg}", "danger")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao criar administrador de escola")
            flash("Ocorreu um erro ao criar o administrador.", "danger")

    return render_template("criar_admin_escola.html")

@user_bp.route("/admins", methods=["GET"])
@login_required
def lista_admins_escola():
    school_id = None
    if hasattr(current_user, 'user_schools') and current_user.user_schools:
        school_id = current_user.user_schools[0].school_id
    
    if not school_id:
        return render_template("listar_admins_escola.html", admins=[])

    rows = db.session.execute(
        select(User)
        .join(UserSchool)
        .where(UserSchool.school_id == school_id, UserSchool.role == 'admin_escola')
        .order_by(User.nome_completo)
    ).scalars().all()

    return render_template("listar_admins_escola.html", admins=rows)