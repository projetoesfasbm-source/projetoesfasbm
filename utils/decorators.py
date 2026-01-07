# utils/decorators.py
from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user
from backend.services.user_service import UserService # Importe o serviço

def sens_required(f):
    """Admin de Ensino (Alunos, Turmas, Horários, Notas) - Verificação Contextual"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        school_id = UserService.get_current_school_id()
        
        # Usa o novo método is_sens_in_school passando o ID
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

def school_admin_or_programmer_required(f):
    """SENS ou Comandante ou Programador"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
            
        school_id = UserService.get_current_school_id()
        
        # Se for SENS na escola atual, ok
        if current_user.is_sens_in_school(school_id):
            return f(*args, **kwargs)
            
        # Se for Admin Geral da escola atual, ok
        if current_user.is_admin_escola_in_school(school_id):
            return f(*args, **kwargs)
            
        if current_user.is_programador:
            return f(*args, **kwargs)

        flash('Permissão insuficiente para gerenciar dados escolares.', 'danger')
        return redirect(url_for('main.dashboard'))
    return decorated_function

# --- DECORADORES AUXILIARES ---

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

def can_schedule_classes_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
            
        school_id = UserService.get_current_school_id()
        
        # Instrutores, SENS, Admin Escola, Programador
        if (current_user.is_instrutor_in_school(school_id) or 
            current_user.is_sens_in_school(school_id) or
            current_user.is_admin_escola_in_school(school_id) or 
            current_user.is_programador):
            return f(*args, **kwargs)
            
        flash('Sem permissão para agendar nesta escola.', 'danger')
        return redirect(url_for('main.dashboard'))
    return decorated_function

# Compatibilidade
admin_escola_required = admin_required