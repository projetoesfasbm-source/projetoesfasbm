# backend/controllers/admin_tools_controller.py

from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user

from utils.decorators import admin_or_programmer_required
from ..services.user_service import UserService
from ..services.admin_tools_service import AdminToolsService

tools_bp = Blueprint('tools', __name__, url_prefix='/ferramentas')

@tools_bp.route('/')
@login_required
@admin_or_programmer_required
def index():
    """Exibe a página principal do módulo de Ferramentas do Administrador."""
    return render_template('ferramentas/index.html')

@tools_bp.route('/reset')
@login_required
@admin_or_programmer_required
def reset_escola():
    """Exibe a página com as opções de reset da escola."""
    return render_template('ferramentas/reset_escola.html')

@tools_bp.route('/limpar', methods=['POST'])
@login_required
@admin_or_programmer_required
def clear_data():
    """Processa as solicitações de limpeza de dados."""
    password = request.form.get('password')
    action = request.form.get('action')
    
    # 1. Validação da senha
    if not password or not current_user.check_password(password):
        flash('Senha incorreta. Nenhuma ação foi executada.', 'danger')
        return redirect(url_for('tools.reset_escola'))

    # 2. Identificação da escola do administrador
    school_id = UserService.get_current_school_id()
    if not school_id:
        flash('Não foi possível identificar a sua escola. Ação cancelada.', 'danger')
        return redirect(url_for('tools.reset_escola'))

    # 3. Execução da ação
    success, message = False, "Ação desconhecida."
    if action == 'clear_students':
        success, message = AdminToolsService.clear_students(school_id)
    elif action == 'clear_instructors':
        success, message = AdminToolsService.clear_instructors(school_id)
    elif action == 'clear_disciplines':
        success, message = AdminToolsService.clear_disciplines(school_id)

    flash(message, 'success' if success else 'danger')
    return redirect(url_for('tools.reset_escola'))