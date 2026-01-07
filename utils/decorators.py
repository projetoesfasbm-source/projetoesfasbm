# utils/decorators.py
from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user

# --- NOVOS DECORADORES ESPECÍFICOS ---

def sens_required(f):
    """Admin de Ensino (Alunos, Turmas, Horários, Notas)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        # SENS manda aqui, Comandante manda, Programador manda.
        if not (current_user.is_sens or current_user.is_admin_escola or current_user.is_programador):
            flash("Acesso restrito à Chefia de Ensino.", "danger")
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def cal_required(f):
    """Admin de Justiça (Punições, Questionários)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        # CAL manda aqui, Comandante manda, Programador manda.
        if not (current_user.is_cal or current_user.is_admin_escola or current_user.is_programador):
            flash("Acesso restrito ao Corpo de Alunos.", "danger")
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# --- DECORADORES LEGADOS (COMPATIBILIDADE) ---
# Aqui garantimos que o código antigo entenda os novos chefes

def school_admin_or_programmer_required(f):
    """
    Este é o decorador mais comum para editar Alunos/Turmas.
    Estamos forçando ele a aceitar o SENS também.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        # SE FOR SENS, DEIXA PASSAR (Pois SENS administra escola)
        if current_user.is_sens:
            return f(*args, **kwargs)
            
        # Regra original (Comandante e Programador)
        if current_user.role not in ['admin_escola', 'programador', 'super_admin']:
            flash('Permissão insuficiente para gerenciar dados escolares.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Admin Geral / Comandante"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not (current_user.is_admin_escola or current_user.is_programador or getattr(current_user, 'role', '') == 'super_admin'):
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
        # SENS e Instrutor agendam aulas
        allowed = ['programador', 'admin_escola', 'instrutor', 'super_admin', 'admin_sens']
        if current_user.role not in allowed:
            flash('Sem permissão para agendar.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def can_view_management_pages_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_or_programmer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        # Staff geral entra
        if current_user.is_staff:
            return f(*args, **kwargs)
        if current_user.role not in ['admin_escola', 'programador']:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def programador_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'programador':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or getattr(current_user, 'role', '') != 'super_admin':
            return redirect(url_for('main.dashboard'))
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