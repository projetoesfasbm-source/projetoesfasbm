# utils/decorators.py
from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user

# --- DECORADORES ESPECÍFICOS DE CARGO (NOVOS) ---

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

# Alias para compatibilidade com códigos antigos
admin_escola_required = admin_required

def cal_required(f):
    """
    Permite acesso para: Admin CAL, Admin Escola e Programador.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        if current_user.role not in ['admin_cal', 'admin_escola', 'programador']:
            flash("Acesso restrito ao Corpo de Alunos (CAL).", "danger")
            return redirect(url_for('main.dashboard'))
            
        return f(*args, **kwargs)
    return decorated_function

def sens_required(f):
    """
    Permite acesso para: Admin SENS, Admin Escola e Programador.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
            
        if current_user.role not in ['admin_sens', 'admin_escola', 'programador']:
            flash("Acesso restrito à Seção de Ensino (SENS).", "danger")
            return redirect(url_for('main.dashboard'))
            
        return f(*args, **kwargs)
    return decorated_function

def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if getattr(current_user, 'role', None) != 'super_admin':
            flash('Você não tem permissão para acessar esta página.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# --- DECORADORES HÍBRIDOS/LEGADOS (ATUALIZADOS PARA INCLUIR SENS/CAL) ---

def admin_or_programmer_required(f):
    """
    Dá acesso a qualquer nível administrativo da escola (CAL, SENS, CHEFE, PROG).
    Usado em páginas de gestão genéricas.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        roles_adm = ['admin_escola', 'programador', 'admin_cal', 'admin_sens', 'super_admin']
        if current_user.role not in roles_adm:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def school_admin_or_programmer_required(f):
    """
    Usado principalmente em edições de Alunos/Turmas.
    Atualizado para permitir acesso ao chefe da SENS também.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        # SENS precisa acessar essas funções de edição de aluno/turma
        allowed_roles = ['programador', 'admin_escola', 'admin_sens', 'super_admin']
        
        if current_user.role not in allowed_roles:
            flash('Você não tem permissão para executar esta ação.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def can_view_management_pages_required(f):
    """
    Permite acesso de leitura/listagem.
    Atualizado para incluir todos os cargos administrativos.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        allowed = [
            'super_admin', 'programador', 'admin_escola', 
            'admin_sens', 'admin_cal', 
            'instrutor', 'aluno'
        ]
        
        if current_user.role not in allowed:
            flash('Você não tem permissão para acessar esta página.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def can_schedule_classes_required(f):
    """
    Permite agendar aulas.
    Atualizado para incluir SENS.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        # SENS agenda aulas, CAL não (geralmente).
        allowed = ['programador', 'admin_escola', 'instrutor', 'super_admin', 'admin_sens']
        
        if current_user.role not in allowed:
            flash('Você não tem permissão para agendar aulas.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def aluno_profile_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.role == 'aluno':
            if not (hasattr(current_user, 'aluno_profile') and current_user.aluno_profile):
                flash('Para continuar, por favor, complete seu perfil de aluno.', 'info')
                return redirect(url_for('aluno.completar_cadastro'))
        return f(*args, **kwargs)
    return decorated_function