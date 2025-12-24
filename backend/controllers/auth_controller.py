# backend/controllers/auth_controller.py

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, current_app, session
)
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, Length
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import select

from ..models.database import db
from ..models.user import User
from ..models.user_school import UserSchool
from ..models.aluno import Aluno
from ..models.instrutor import Instrutor
from ..models.turma import Turma
from ..services.email_service import EmailService

from utils.normalizer import normalize_matricula, normalize_name

auth_bp = Blueprint("auth", __name__, url_prefix="")

# --- Forms (Mantidos) ---
class CSRFOnlyForm(FlaskForm): pass

class LoginForm(FlaskForm):
    username = StringField("Usuário", validators=[DataRequired()])
    password = PasswordField("Senha", validators=[DataRequired()])
    remember = BooleanField("Lembrar-me")
    submit = SubmitField("Entrar")

class RequestResetForm(FlaskForm):
    email = StringField("E-mail", validators=[DataRequired(), Email()])
    submit = SubmitField("Enviar link de redefinição")

class ResetPasswordForm(FlaskForm):
    password = PasswordField("Nova senha", validators=[DataRequired(), Length(min=8)])
    password2 = PasswordField("Confirme a senha", validators=[DataRequired(), EqualTo("password")])
    submit = SubmitField("Redefinir senha")

# --- Helpers ---
def _get_serializer():
    secret = current_app.config.get("SECRET_KEY") or "CHANGEME"
    return URLSafeTimedSerializer(secret_key=secret, salt="reset-password")

def _find_user_for_login(identifier):
    ident = (identifier or "").strip()
    if not ident: return None
    mat_norm = normalize_matricula(ident)
    if mat_norm:
        user = db.session.execute(select(User).where(User.matricula == mat_norm)).scalar_one_or_none()
        if user: return user
    if "@" in ident:
        user = db.session.execute(select(User).where(User.email == ident.lower())).scalar_one_or_none()
        if user: return user
    user = db.session.execute(select(User).where(User.username == ident)).scalar_one_or_none()
    return user

# --- Rotas ---

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        identifier = form.username.data.strip()
        password = form.password.data
        remember = bool(form.remember.data)

        user = _find_user_for_login(identifier)
        if not user or not user.check_password(password):
            flash("Credenciais inválidas.", "danger")
            return render_template("login.html", form=form)

        if not user.is_active:
            flash("Conta inativa.", "warning")
            return redirect(url_for("auth.register"))

        login_user(user, remember=remember)
        
        # Limpa qualquer seleção anterior
        session.pop('active_school_id', None)
        
        # === AQUI ESTÁ A LÓGICA DO MODAL/SELEÇÃO ===
        # Verifica quantas escolas o usuário tem
        user_schools = user.user_schools # Relação SQLAlchemy
        
        if len(user_schools) > 1:
            # Se tiver mais de uma, NÃO vai pro dashboard. Vai pra seleção.
            return redirect(url_for('auth.select_school'))
        
        elif len(user_schools) == 1:
            # Se tiver só uma, define ela e vai pro dashboard
            session['active_school_id'] = user_schools[0].school_id
            session.permanent = True
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for("main.dashboard"))
            
        else:
            # Caso raríssimo: usuário sem escola nenhuma
            flash("Login realizado, mas você não está vinculado a nenhuma escola.", "warning")
            return redirect(url_for("main.dashboard"))

    return render_template("login.html", form=form)

# ROTA NOVA: Exibe o "Modal" de seleção
@auth_bp.route("/select-school")
@login_required
def select_school():
    # Busca as escolas do usuário logado para exibir no modal
    schools = current_user.user_schools
    return render_template("select_school.html", schools=schools)

# ROTA NOVA: Processa a escolha e manda pro Dashboard
@auth_bp.route("/set-school/<int:school_id>")
@login_required
def set_school(school_id):
    # Verifica segurança: O usuário tem essa escola?
    valid = False
    for us in current_user.user_schools:
        if us.school_id == school_id:
            valid = True
            break
    
    if valid:
        session['active_school_id'] = school_id
        session.permanent = True # Cookie persistente
        flash("Escola selecionada com sucesso.", "success")
        return redirect(url_for("main.dashboard"))
    else:
        flash("Erro ao selecionar escola.", "danger")
        return redirect(url_for("auth.login"))

@auth_bp.route("/logout")
@login_required
def logout():
    session.pop('active_school_id', None)
    logout_user()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("auth.login"))

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    turmas = db.session.scalars(select(Turma).order_by(Turma.nome)).all()
    form_data = request.form.to_dict()

    if request.method == "POST":
        role = form_data.get("role", "aluno")
        pwd = form_data.get("password", "")
        pwd2 = form_data.get("password2", "")

        if not pwd or pwd != pwd2 or len(pwd) < 8:
            flash("Senha inválida.", "danger")
            return render_template("register.html", form_data=form_data, turmas=turmas)

        matricula_norm = normalize_matricula(form_data.get("matricula"))
        if not matricula_norm:
            flash("Matrícula inválida.", "danger")
            return render_template("register.html", form_data=form_data, turmas=turmas)

        user = db.session.execute(select(User).where(User.matricula == matricula_norm)).scalar_one_or_none()
        if not user:
            flash("Matrícula não encontrada.", "danger")
            return render_template("register.html", form_data=form_data, turmas=turmas)

        vinculos = db.session.scalars(select(UserSchool).where(UserSchool.user_id == user.id)).all()
        if not vinculos:
            flash("Sem vínculo escolar.", "danger")
            return render_template("register.html", form_data=form_data, turmas=turmas)
        
        primeira_escola_id = vinculos[0].school_id

        user.role = role
        user.nome_completo = normalize_name(form_data.get("nome_completo"))
        user.nome_de_guerra = normalize_name(form_data.get("nome_de_guerra"))
        user.posto_graduacao = form_data.get("posto_graduacao") or None
        user.email = (form_data.get("email") or "").strip().lower() or None
        user.set_password(pwd)
        user.is_active = True
        user.must_change_password = False

        if role == "aluno":
            opm_value = form_data.get("opm", "Não informado")
            turma_id_value = form_data.get('turma_id')
            turma_id = int(turma_id_value) if turma_id_value else None
            
            if not user.aluno_profile:
                perfil = Aluno(user_id=user.id, opm=opm_value, turma_id=turma_id)
                db.session.add(perfil)
            else:
                user.aluno_profile.opm = opm_value
                user.aluno_profile.turma_id = turma_id

        if role == "instrutor":
            if not user.instrutor_profile:
                db.session.add(Instrutor(user_id=user.id, school_id=primeira_escola_id))

        try:
            db.session.commit()
            flash("Conta ativada!", "success")
            return redirect(url_for("auth.login"))
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ativar")
            flash("Erro ao ativar conta.", "danger")
            return render_template("register.html", form_data=form_data, turmas=turmas)

    return render_template("register.html", form_data={}, turmas=turmas)

@auth_bp.route("/recuperar-senha", methods=["GET", "POST"])
def recuperar_senha():
    form = RequestResetForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = db.session.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if not user:
            flash("Se o e-mail existir, você receberá instruções.", "info")
            return redirect(url_for("auth.recuperar_senha"))

        s = _get_serializer()
        token = s.dumps({"user_id": user.id})
        EmailService.send_password_reset_email(user, token)
        flash("Se o e-mail existir, você receberá instruções.", "info")
        return redirect(url_for("auth.login"))
    return render_template("recuperar_senha.html", form=form)

@auth_bp.route("/redefinir-senha/<token>", methods=["GET", "POST"])
def redefinir_senha(token):
    form = ResetPasswordForm()
    s = _get_serializer()
    user_id = None
    try:
        data = s.loads(token, max_age=3600)
        user_id = data.get("user_id")
    except (SignatureExpired, BadSignature):
        flash("Token inválido.", "warning")
        return redirect(url_for("auth.recuperar_senha"))

    user = db.session.get(User, user_id)
    if not user:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for("auth.recuperar_senha"))

    if form.validate_on_submit():
        try:
            user.set_password(form.password.data)
            user.must_change_password = False
            db.session.commit()
            flash("Senha redefinida.", "success")
            return redirect(url_for("auth.login"))
        except Exception:
            db.session.rollback()
            flash("Erro ao redefinir.", "danger")

    return render_template("redefinir_senha.html", form=form, token=token)