# utils/decorators.py
from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user

def programador_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'programador':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Exige ser Admin Geral da Escola (ou Programador)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.role not in ['admin_escola', 'programador']:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def cal_required(f):
    """
    Permite acesso para:
    1. Admin CAL (Corpo de Alunos)
    2. Admin Escola (Chefe)
    3. Programador
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        # Lista de roles permitidas no CAL
        # Inclui admin_escola e programador para que eles possam acessar/corrigir
        if current_user.role not in ['admin_cal', 'admin_escola', 'programador']:
            flash("Acesso restrito ao Corpo de Alunos (CAL).", "danger")
            return redirect(url_for('main.dashboard'))
            
        return f(*args, **kwargs)
    return decorated_function

def sens_required(f):
    """
    Permite acesso para:
    1. Admin SENS (Seção de Ensino)
    2. Admin Escola (Chefe)
    3. Programador
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
            
        # Lista de roles permitidas na SENS
        if current_user.role not in ['admin_sens', 'admin_escola', 'programador']:
            flash("Acesso restrito à Seção de Ensino (SENS).", "danger")
            return redirect(url_for('main.dashboard'))
            
        return f(*args, **kwargs)
    return decorated_function

def admin_or_programmer_required(f):
    """
    Dá acesso a qualquer nível administrativo (CAL, SENS, CHEFE, PROG).
    Usado em rotas comuns ou genéricas de administração.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        roles_adm = ['admin_escola', 'programador', 'admin_cal', 'admin_sens']
        if current_user.role not in roles_adm:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function