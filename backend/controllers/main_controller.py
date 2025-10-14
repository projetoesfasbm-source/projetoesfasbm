# backend/controllers/main_controller.py

from __future__ import annotations

import re
from typing import List

from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_required, current_user

from ..models.user import User
from ..models.school import School
from ..models.database import db
from ..services.dashboard_service import DashboardService
from utils.decorators import admin_or_programmer_required
from ..services.user_service import UserService
from utils.normalizer import normalize_matricula

main_bp = Blueprint('main', __name__)

# ---------------------------------------
# Utils de parsing para pré-cadastro
# ---------------------------------------

# aceita vírgula, espaços (inclui quebras de linha), ponto-e-vírgula
_SPLIT_RE = re.compile(r"[,\s;]+")

def _parse_matriculas(raw: str) -> List[str]:
    """
    Recebe string com várias matrículas separadas por vírgula/espacos/;/\n.
    Normaliza, remove vazios e duplicados preservando a ordem.
    Obs.: NÃO filtramos por isdigit() para não descartar formatos alfanuméricos.
          Se quiser restringir a números, ative isso dentro do normalize_matricula.
    """
    if not raw:
        return []
    itens = [x.strip() for x in _SPLIT_RE.split(raw) if x.strip()]
    # normaliza
    itens = [normalize_matricula(x) for x in itens]
    # remove duplicadas preservando ordem
    seen = set()
    result: List[str] = []
    for m in itens:
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result


@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    # Ao sair de super_admin/programador, limpa "ver como"
    if current_user.role not in ['super_admin', 'programador']:
        session.pop('view_as_school_id', None)
        session.pop('view_as_school_name', None)

    view_as_school_id = request.args.get('view_as_school', type=int)

    if current_user.role in ['super_admin', 'programador'] and view_as_school_id:
        school = db.session.get(School, view_as_school_id)
        if school:
            session['view_as_school_id'] = school.id
            session['view_as_school_name'] = school.nome
        else:
            flash("Escola selecionada para visualização não encontrada.", "danger")
            return redirect(url_for('super_admin.dashboard'))

    school_id_to_load = None
    if current_user.role in ['super_admin', 'programador']:
        school_id_to_load = session.get('view_as_school_id')
    elif getattr(current_user, 'schools', None):
        # current_user.schools é @property -> lista derivada de user_schools
        if current_user.schools:
            school_id_to_load = current_user.schools[0].id

    dashboard_data = DashboardService.get_dashboard_data(school_id=school_id_to_load)

    school_in_context = None
    if school_id_to_load:
        school_in_context = db.session.get(School, school_id_to_load)

    return render_template(
        'dashboard.html',
        dashboard_data=dashboard_data,
        school_in_context=school_in_context
    )


@main_bp.route('/pre-cadastro', methods=['GET', 'POST'])
@login_required
@admin_or_programmer_required
def pre_cadastro():
    """
    Pré-cadastro (unitário ou em lote) de usuários por matrícula,
    vinculando-os à escola atual do administrador (ou programador).
    - GET: exibe o formulário (template: pre_cadastro.html)
    - POST: processa e chama UserService.(pre_register_user|batch_pre_register_users)
    """
    # role pode vir por querystring para pré-seleção no template
    role_arg = request.args.get('role')

    if request.method == 'POST':
        # 1) Identifica a escola do usuário logado
        school_id = UserService.get_current_school_id()
        if not school_id:
            flash("Não foi possível identificar a escola do administrador. Ação cancelada.", "danger")
            return redirect(url_for('main.pre_cadastro', role=role_arg) if role_arg else url_for('main.pre_cadastro'))

        # 2) Determina a role
        # prioridade: role do form > role da URL > 'aluno'
        role = (request.form.get('role') or role_arg or 'aluno').strip()
        if role not in {'aluno', 'instrutor', 'admin_escola'}:
            flash('Função inválida para pré-cadastro.', 'danger')
            return redirect(url_for('main.pre_cadastro', role=role_arg) if role_arg else url_for('main.pre_cadastro'))

        # 3) Lê e normaliza as matrículas
        raw = (request.form.get('matriculas') or '').strip()
        matriculas = _parse_matriculas(raw)

        if not matriculas:
            # fallback: permitir um único valor direto (campo antigo)
            unico = normalize_matricula((request.form.get('matricula') or '').strip())
            if unico:
                matriculas = [unico]

        if not matriculas:
            flash('Informe pelo menos uma matrícula.', 'warning')
            return redirect(url_for('main.pre_cadastro', role=role_arg) if role_arg else url_for('main.pre_cadastro'))

        # 4) Decide unitário vs. lote
        if len(matriculas) == 1:
            form_data = {
                'matricula': matriculas[0],
                'role': role,
            }
            success, message = UserService.pre_register_user(form_data, school_id)
            if success:
                flash(message, 'success')
            else:
                flash(message or 'Erro ao pré-cadastrar usuário.', 'danger')
        else:
            success, novos, existentes = UserService.batch_pre_register_users(matriculas, role, school_id)
            if success:
                flash(f'Pré-cadastro concluído: {novos} novo(s), {existentes} já existente(s). Função: {role}.', 'success')
            else:
                flash('Falha ao pré-cadastrar usuários em lote. Verifique o log.', 'danger')

        return redirect(url_for('main.pre_cadastro', role=role_arg) if role_arg else url_for('main.pre_cadastro'))

    # GET: carrega escolas só para exibição no template (ele mostra a lista quando apropriado)
    schools = db.session.query(School).order_by(School.nome).all()
    return render_template('pre_cadastro.html', role_predefinido=role_arg, schools=schools)
