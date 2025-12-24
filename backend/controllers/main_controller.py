# backend/controllers/main_controller.py

from __future__ import annotations

import re
from typing import List

from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app
from flask_login import login_required, current_user

from ..models.user import User
from ..models.school import School
from ..models.user_school import UserSchool # Necessário para query direta
from ..models.database import db
from ..services.dashboard_service import DashboardService
from utils.decorators import admin_or_programmer_required
from ..services.user_service import UserService
from utils.normalizer import normalize_matricula

main_bp = Blueprint('main', __name__)

# ---------------------------------------
# Context Processor
# ---------------------------------------
@main_bp.context_processor
def inject_active_school():
    if current_user.is_authenticated:
        school_id = UserService.get_current_school_id()
        current_school = db.session.get(School, school_id) if school_id else None
        return dict(
            current_school_id=school_id, 
            current_school=current_school,
            active_school=current_school 
        )
    return dict(current_school_id=None, current_school=None, active_school=None)

# ---------------------------------------
# Utils
# ---------------------------------------
_SPLIT_RE = re.compile(r"[,\s;]+")

def _parse_matriculas(raw: str) -> List[str]:
    if not raw: return []
    itens = [x.strip() for x in _SPLIT_RE.split(raw) if x.strip()]
    itens = [normalize_matricula(x) for x in itens]
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

@main_bp.route('/selecionar-escola')
@login_required
def selecionar_escola():
    """
    Rota obrigatória quando o usuário possui múltiplos vínculos e
    ainda não definiu em qual contexto quer trabalhar.
    """
    # Busca todas as escolas vinculadas ao usuário
    vinculos = db.session.execute(
        db.select(UserSchool)
        .where(UserSchool.user_id == current_user.id)
        .order_by(UserSchool.school_id)
    ).scalars().all()
    
    escolas_list = []
    for v in vinculos:
        s = db.session.get(School, v.school_id)
        if s:
            escolas_list.append({
                'id': s.id,
                'nome': s.nome,
                'role': v.role  # Útil mostrar qual papel ele tem na escola
            })

    # Se por acaso só tem 1, já seleciona e vai pro dashboard
    if len(escolas_list) == 1:
        UserService.set_active_school(escolas_list[0]['id'])
        return redirect(url_for('main.dashboard'))

    return render_template('select_school.html', escolas=escolas_list)

@main_bp.route('/trocar-escola/<int:school_id>')
@login_required
def trocar_escola(school_id):
    """
    Rota para forçar a mudança de contexto (Isolamento).
    """
    success = UserService.set_active_school(school_id)
    if success:
        flash("Contexto escolar alterado com sucesso.", "success")
        return redirect(url_for('main.dashboard'))
    else:
        flash("Você não tem permissão para acessar esta escola.", "danger")
        return redirect(url_for('main.selecionar_escola'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    # 1. Verifica Super Admin "View As"
    if current_user.role in ['super_admin', 'programador']:
        view_as_school_id = request.args.get('view_as_school', type=int)
        if view_as_school_id:
            school = db.session.get(School, view_as_school_id)
            if school:
                session['view_as_school_id'] = school.id
                session['view_as_school_name'] = school.nome
            else:
                flash("Escola selecionada para visualização não encontrada.", "danger")
                return redirect(url_for('super_admin.dashboard'))
    else:
        session.pop('view_as_school_id', None)
        session.pop('view_as_school_name', None)

    # 2. Obtém escola atual (Strict Mode)
    school_id_to_load = UserService.get_current_school_id()

    # 3. Se retornou None, significa ambiguidade -> Vai para Seleção
    if not school_id_to_load:
        return redirect(url_for('main.selecionar_escola'))

    # 4. Carrega Dashboard
    dashboard_data = DashboardService.get_dashboard_data(school_id=school_id_to_load)

    school_in_context = None
    if school_id_to_load:
        school_in_context = db.session.get(School, school_id_to_load)

    return render_template(
        'dashboard.html',
        dashboard_data=dashboard_data,
        school_in_context=school_in_context
    )

@main_bp.route('/safebrowser')
@login_required
def safebrowser():
    return render_template('safebrowser.html')

@main_bp.route('/pre-cadastro', methods=['GET', 'POST'])
@login_required
@admin_or_programmer_required
def pre_cadastro():
    role_arg = request.args.get('role')

    if request.method == 'POST':
        school_id = UserService.get_current_school_id()
        if not school_id:
            flash("Escola não selecionada.", "danger")
            return redirect(url_for('main.selecionar_escola'))

        role = (request.form.get('role') or role_arg or 'aluno').strip()
        if role not in {'aluno', 'instrutor', 'admin_escola'}:
            flash('Função inválida para pré-cadastro.', 'danger')
            return redirect(url_for('main.pre_cadastro', role=role_arg))

        raw = (request.form.get('matriculas') or '').strip()
        matriculas = _parse_matriculas(raw)

        if not matriculas:
            unico = normalize_matricula((request.form.get('matricula') or '').strip())
            if unico:
                matriculas = [unico]

        if not matriculas:
            flash('Informe pelo menos uma matrícula.', 'warning')
            return redirect(url_for('main.pre_cadastro', role=role_arg))

        if len(matriculas) == 1:
            form_data = {'matricula': matriculas[0], 'role': role}
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
                flash('Falha ao pré-cadastrar usuários em lote.', 'danger')

        return redirect(url_for('main.pre_cadastro', role=role_arg))

    schools = db.session.query(School).order_by(School.nome).all()
    return render_template('pre_cadastro.html', role_predefinido=role_arg, schools=schools)