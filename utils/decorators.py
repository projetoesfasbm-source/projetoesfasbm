# utils/decorators.py
from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user
from backend.services.user_service import UserService

def sens_required(f):
    """Admin de Ensino (Alunos, Turmas, Horários, Notas) - Verificação Contextual"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        school_id = UserService.get_current_school_id()
        if not current_user.is_sens_in_school(school_id):
            flash("Acesso restrito à Chefia de Ensino nesta escola.", "danger")
            return redirect(url_for('main.dashboard'))
            
        return f(*args, **kwargs)
    return decorated_function

def cal_required(f):
    """Admin de Justiça (Punições, Questionários) - Verificação Contextual"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
            
        school_id = UserService.get_current_school_id()
        if not current_user.is_cal_in_school(school_id):
            flash("Acesso restrito ao Corpo de Alunos nesta escola.", "danger")
            return redirect(url_for('main.dashboard'))
            
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Admin Geral da Escola (Comandante)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
            
        school_id = UserService.get_current_school_id()
        if not current_user.is_admin_escola_in_school(school_id):
             abort(403)
        return f(*args, **kwargs)
    return decorated_function

# Alias para compatibilidade
admin_escola_required = admin_required

def can_schedule_classes_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
            
        school_id = UserService.get_current_school_id()
        
        # --- VERIFICAÇÃO ORIGINAL (Provável causa do erro para CAL) ---
        is_instrutor = current_user.is_instrutor_in_school(school_id)
        is_sens = current_user.is_sens_in_school(school_id)
        is_admin = current_user.is_admin_escola_in_school(school_id)
        is_prog = current_user.is_programador
        
        # Tenta verificar se tem perfil, mesmo que a Role seja diferente
        has_instrutor_profile = getattr(current_user, 'instrutor_profile', None) is not None

        # CORREÇÃO LÓGICA: Se tiver perfil de instrutor, libera, mesmo sendo CAL/Outro
        if (is_instrutor or is_sens or is_admin or is_prog or has_instrutor_profile):
            return f(*args, **kwargs)
            
        # --- DEBUG (PRONT) ATIVADO ---
        # Se cair aqui, mostra exatamente o que falhou
        debug_msg = (
            f"DEBUG PERMISSÃO: Role='{current_user.role}' | "
            f"School_ID={school_id} | "
            f"Check_Instrutor={is_instrutor} | "
            f"Tem_Perfil_Instrutor={has_instrutor_profile}"
        )
        flash(debug_msg, 'danger')
        # flash('Sem permissão para agendar nesta escola.', 'danger') # Original comentada
        
        return redirect(url_for('main.dashboard'))
    return decorated_function

def admin_or_programmer_required(f):
    """
    Usado em admin_tools e vinculos.
    Permite acesso se for Admin da Escola, Staff (SENS/CAL) ou Programador.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        school_id = UserService.get_current_school_id()
        if current_user.is_staff_in_school(school_id):
            return f(*args, **kwargs)
            
        abort(403)
        return f(*args, **kwargs)
    return decorated_function

def school_admin_or_programmer_required(f):
    """
    Permite acesso ao SENS, Admin da Escola (Comandante) ou Programador.
    Usado no AlunoController.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
            
        school_id = UserService.get_current_school_id()
        
        if (current_user.is_programador or 
            current_user.is_admin_escola_in_school(school_id) or 
            current_user.is_sens_in_school(school_id)):
            return f(*args, **kwargs)

        flash('Permissão insuficiente para gerenciar dados escolares.', 'danger')
        return redirect(url_for('main.dashboard'))
    return decorated_function

def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or getattr(current_user, 'role', '') != 'super_admin':
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def programador_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_programador:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def can_view_management_pages_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def aluno_profile_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated: return redirect(url_for('auth.login'))
        if current_user.role == 'aluno' and not (hasattr(current_user, 'aluno_profile') and current_user.aluno_profile):
            return redirect(url_for('aluno.completar_cadastro'))
        return f(*args, **kwargs)
    return decorated_function