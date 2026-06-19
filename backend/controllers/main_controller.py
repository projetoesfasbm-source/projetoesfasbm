# backend/controllers/main_controller.py

from __future__ import annotations

import re
from typing import List

from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app
from flask_login import login_required, current_user
from sqlalchemy import select, or_

from ..models.user import User
from ..models.school import School
from ..models.user_school import UserSchool
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
    from flask import g, session
    context = {
        'current_school_id': None, 
        'current_school': None,
        'active_school': None,
        'user_allowed_schools': []
    }
    
    if current_user.is_authenticated:
        active = g.get('active_school')
        context['current_school'] = active
        context['active_school'] = active
        context['current_school_id'] = active.id if active else None
        
        # --- NOVA LÓGICA: Lista de escolas para o Switcher no Topo ---
        # Escondido de alunos
        if current_user.role != 'aluno':
            # Usa cache na sessão para não deixar o site lento a cada clique
            if 'user_schools_cache' in session:
                context['user_allowed_schools'] = session['user_schools_cache']
            else:
                escolas_dict = {}
                
                # Se for super admin, tem acesso a tudo
                if getattr(current_user, 'is_super_admin', False) or current_user.role == 'super_admin':
                    todas = db.session.scalars(select(School).order_by(School.nome)).all()
                    for s in todas: escolas_dict[s.id] = {'id': s.id, 'nome': s.nome}
                else:
                    # Vinculos diretos (Admin, SENS)
                    vinculos = db.session.scalars(select(UserSchool).where(UserSchool.user_id == current_user.id)).all()
                    for v in vinculos:
                        s = db.session.get(School, v.school_id)
                        if s: escolas_dict[s.id] = {'id': s.id, 'nome': s.nome}
                        
                    # Vínculos indiretos (Instrutor vinculado a turmas)
                    from ..models.instrutor import Instrutor
                    from ..models.disciplina_turma import DisciplinaTurma
                    from ..models.disciplina import Disciplina
                    from ..models.turma import Turma
                    
                    instrutores = db.session.scalars(select(Instrutor).where(Instrutor.user_id == current_user.id)).all()
                    if instrutores:
                        instrutor_ids = [i.id for i in instrutores]
                        if instrutor_ids:
                            turmas_instrutor = db.session.scalars(
                                select(Turma)
                                .join(Disciplina, Disciplina.turma_id == Turma.id)
                                .join(DisciplinaTurma, DisciplinaTurma.disciplina_id == Disciplina.id)
                                .where(
                                    or_(
                                        DisciplinaTurma.instrutor_id_1.in_(instrutor_ids),
                                        DisciplinaTurma.instrutor_id_2.in_(instrutor_ids)
                                    )
                                )
                            ).all()
                            for t in turmas_instrutor:
                                if t.school_id and t.school_id not in escolas_dict:
                                    s = db.session.get(School, t.school_id)
                                    if s: escolas_dict[s.id] = {'id': s.id, 'nome': s.nome}
                
                lista_escolas = sorted(list(escolas_dict.values()), key=lambda x: x['nome'])
                session['user_schools_cache'] = lista_escolas
                context['user_allowed_schools'] = lista_escolas
                
    return context

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
    escolas_dict = {}

    vinculos = db.session.execute(
        select(UserSchool).where(UserSchool.user_id == current_user.id).order_by(UserSchool.school_id)
    ).scalars().all()
    
    for v in vinculos:
        s = db.session.get(School, v.school_id)
        if s:
            escolas_dict[s.id] = {
                'id': s.id,
                'nome': s.nome,
                'role': v.role 
            }

    from ..models.instrutor import Instrutor
    from ..models.disciplina_turma import DisciplinaTurma
    from ..models.disciplina import Disciplina
    from ..models.turma import Turma

    instrutores = db.session.scalars(select(Instrutor).where(Instrutor.user_id == current_user.id)).all()
    if instrutores:
        instrutor_ids = [i.id for i in instrutores]
        turmas_instrutor = db.session.scalars(
            select(Turma)
            .join(Disciplina, Disciplina.turma_id == Turma.id)
            .join(DisciplinaTurma, DisciplinaTurma.disciplina_id == Disciplina.id)
            .where(
                or_(
                    DisciplinaTurma.instrutor_id_1.in_(instrutor_ids),
                    DisciplinaTurma.instrutor_id_2.in_(instrutor_ids)
                )
            )
        ).all()
        
        for t in turmas_instrutor:
            if t.school_id and t.school_id not in escolas_dict:
                s = db.session.get(School, t.school_id)
                if s:
                    escolas_dict[s.id] = {'id': s.id, 'nome': s.nome, 'role': 'instrutor'}

    if current_user.role == 'aluno' and getattr(current_user, 'aluno_profile', None) and current_user.aluno_profile.turma:
        t = current_user.aluno_profile.turma
        if t.school_id and t.school_id not in escolas_dict:
            s = db.session.get(School, t.school_id)
            if s:
                escolas_dict[s.id] = {'id': s.id, 'nome': s.nome, 'role': 'aluno'}

    escolas_list = list(escolas_dict.values())
    escolas_list.sort(key=lambda x: x['nome'])

    if len(escolas_list) == 1:
        UserService.set_active_school(escolas_list[0]['id'])
        return redirect(url_for('main.dashboard'))

    return render_template('select_school.html', escolas=escolas_list)

@main_bp.route('/trocar-escola/<int:school_id>')
@login_required
def trocar_escola(school_id):
    """
    Rota para forçar a mudança de contexto (Isolamento).
    Agora usa request.referrer para manter o usuário na tela atual!
    """
    if current_user.role == 'super_admin' and session.get('is_dec_mode'):
        session['active_school_id'] = school_id
        session.permanent = True
        flash("Contexto escolar alterado com sucesso.", "success")
        # Mantém na mesma página
        return redirect(request.referrer or url_for('main.dashboard'))
        
    success = UserService.set_active_school(school_id)
    if success:
        flash("Contexto escolar alterado com sucesso.", "success")
        # Mantém na mesma página
        return redirect(request.referrer or url_for('main.dashboard'))
    else:
        flash("Você não tem permissão para acessar esta escola.", "danger")
        return redirect(url_for('main.selecionar_escola'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    dec_mode_active = session.get('is_dec_mode', False) and current_user.role == 'super_admin'
    
    if current_user.role != 'super_admin':
        session.pop('is_dec_mode', None)

    if dec_mode_active:
        view_as_school_id = request.args.get('view_as_school', type=int)
        
        if view_as_school_id:
            school = db.session.get(School, view_as_school_id)
            if school:
                session['view_as_school_id'] = school.id
                session['view_as_school_name'] = school.nome
                session['active_school_id'] = school.id 
                return redirect(url_for('main.dashboard'))
            else:
                flash("Escola selecionada não encontrada.", "danger")
                return redirect(url_for('super_admin.dashboard'))

        elif not session.get('active_school_id'):
            return redirect(url_for('super_admin.dashboard'))

    else:
        session.pop('view_as_school_id', None)
        session.pop('view_as_school_name', None)

    if current_user.role == 'super_admin' and not dec_mode_active and not session.get('active_school_id'):
        return redirect(url_for('main.selecionar_escola'))

    school_id_to_load = session.get('view_as_school_id') or session.get('active_school_id') or UserService.get_current_school_id()

    if not school_id_to_load:
        return redirect(url_for('main.selecionar_escola'))

    try:
        active_edicao_id = session.get('active_edicao_id')
        dashboard_data = DashboardService.get_dashboard_data(school_id=school_id_to_load, edicao_id=active_edicao_id)
    except Exception as e:
        print(f"Erro silenciado no DashboardService: {e}")
        dashboard_data = {
            'total_alunos': 0, 'total_instrutores': 0, 'total_disciplinas': 0, 
            'aulas_pendentes': 0, 'lista_aulas_pendentes': [],
            'lista_processos_pendentes': [], 'usuarios_recentes': [],
            'proximas_aulas': []
        }

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

    valid_roles = {'aluno', 'instrutor', 'admin_escola'}
    if role_arg and role_arg not in valid_roles:
        role_arg = None 

    if request.method == 'POST':
        school_id = UserService.get_current_school_id()
        if not school_id:
            flash("Escola não selecionada.", "danger")
            return redirect(url_for('main.selecionar_escola'))
            
        active_edicao_id = session.get('active_edicao_id')

        role = (request.form.get('role') or role_arg or 'aluno').strip()
        if role not in valid_roles:
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

        edicao_id_to_pass = active_edicao_id if role == 'aluno' else None

        if role == 'aluno' and not edicao_id_to_pass:
             flash("Você precisa selecionar uma edição ativa para pré-cadastrar alunos.", "danger")
             return redirect(url_for('main.pre_cadastro', role=role_arg))

        if len(matriculas) == 1:
            form_data = {'matricula': matriculas[0], 'role': role}
            success, message = UserService.pre_register_user(form_data, school_id, edicao_id=edicao_id_to_pass)
            if success:
                flash(message, 'success')
            else:
                flash(message or 'Erro ao pré-cadastrar usuário.', 'danger')
        else:
            success, novos, existentes = UserService.batch_pre_register_users(matriculas, role, school_id, edicao_id=edicao_id_to_pass)
            if success:
                flash(f'Pré-cadastro concluído: {novos} novo(s), {existentes} já existente(s). Função: {role}.', 'success')
            else:
                flash('Falha ao pré-cadastrar usuários em lote.', 'danger')

        return redirect(url_for('main.pre_cadastro', role=role_arg))

    schools = db.session.query(School).order_by(School.nome).all()
    return render_template('pre_cadastro.html', role_predefinido=role_arg, schools=schools)
