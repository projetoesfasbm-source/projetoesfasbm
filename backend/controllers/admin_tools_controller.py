# backend/controllers/admin_tools_controller.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, send_file
from flask_login import login_required, current_user
import io
from datetime import datetime

from utils.decorators import admin_or_programmer_required
from ..services.user_service import UserService
from ..services.admin_tools_service import AdminToolsService
from ..services.mail_merge_service import MailMergeService # <-- NOVA IMPORTAÇÃO

tools_bp = Blueprint('tools', __name__, url_prefix='/ferramentas')

@tools_bp.route('/')
@login_required
@admin_or_programmer_required
def index():
    """Exibe a página principal do módulo de Ferramentas do Administrador."""
    return render_template('ferramentas/index.html')

# --- NOVA ROTA PARA MALA DIRETA ---
@tools_bp.route('/mail-merge', methods=['GET', 'POST'])
@login_required
@admin_or_programmer_required
def mail_merge():
    if request.method == 'POST':
        template_file = request.files.get('template_file')
        data_file = request.files.get('data_file')
        output_format = request.form.get('output_format', 'docx')

        if not template_file or not data_file:
            flash('Ambos os arquivos (template e dados) são obrigatórios.', 'danger')
            return redirect(url_for('tools.mail_merge'))

        zip_buffer, error = MailMergeService.generate_documents(template_file, data_file, output_format)

        if error:
            flash(f'Ocorreu um erro ao gerar os documentos: {error}', 'danger')
            return redirect(url_for('tools.mail_merge'))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=f'documentos_gerados_{timestamp}.zip',
            mimetype='application/zip'
        )

    return render_template('ferramentas/mail_merge.html')
# --- FIM DA NOVA ROTA ---

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