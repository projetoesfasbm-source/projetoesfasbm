# backend/controllers/admin_tools_controller.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, send_file
from flask_login import login_required, current_user
import io
from datetime import datetime, timedelta

from utils.decorators import admin_or_programmer_required, admin_escola_required
from ..services.user_service import UserService
from ..services.admin_tools_service import AdminToolsService
from ..services.mail_merge_service import MailMergeService
from ..services.log_service import LogService

tools_bp = Blueprint('tools', __name__, url_prefix='/ferramentas')

@tools_bp.route('/')
@login_required
@admin_or_programmer_required
def index():
    """Exibe a página principal do módulo de Ferramentas do Administrador."""
    return render_template('ferramentas/index.html')

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

        # A função agora retorna um buffer de arquivo ZIP
        zip_buffer, error = MailMergeService.generate_documents(template_file, data_file, output_format)

        if error:
            flash(f'Ocorreu um erro ao gerar os documentos: {error}', 'danger')
            return redirect(url_for('tools.mail_merge'))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Ajusta o send_file para enviar um arquivo .zip
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=f'certificados_gerados_{timestamp}.zip',
            mimetype='application/zip'
        )

    return render_template('ferramentas/mail_merge.html')

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
    
    if not password or not current_user.check_password(password):
        flash('Senha incorreta. Nenhuma ação foi executada.', 'danger')
        return redirect(url_for('tools.reset_escola'))

    school_id = UserService.get_current_school_id()
    if not school_id:
        flash('Não foi possível identificar a sua escola. Ação cancelada.', 'danger')
        return redirect(url_for('tools.reset_escola'))

    success, message = False, "Ação desconhecida."
    if action == 'clear_students':
        success, message = AdminToolsService.clear_students(school_id)
    elif action == 'clear_instructors':
        success, message = AdminToolsService.clear_instructors(school_id)
    elif action == 'clear_disciplines':
        success, message = AdminToolsService.clear_disciplines(school_id)

    flash(message, 'success' if success else 'danger')
    return redirect(url_for('tools.reset_escola'))

# --- NOVA FUNCIONALIDADE: LOGS DE AUDITORIA ---
@tools_bp.route('/logs')
@login_required
@admin_or_programmer_required # Permite que Admin Escola e Programador vejam os logs
def logs_admin():
    school_id = UserService.get_current_school_id()
    if not school_id:
        flash("Nenhuma escola selecionada.", "warning")
        return redirect(url_for('main.dashboard'))

    # Filtros da URL
    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')
    filtro_user_id = request.args.get('user_id', type=int)

    # Converter datas
    if data_inicio_str:
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d')
    else:
        data_inicio = datetime.now() - timedelta(days=7)
    
    if data_fim_str:
        # Ajuste para pegar o final do dia na data fim
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    else:
        data_fim = datetime.now()

    # Buscar Logs
    logs = LogService.get_logs(
        school_id=school_id, 
        date_start=data_inicio, 
        date_end=data_fim, 
        user_id=filtro_user_id,
        limit=200 # Limite de segurança para performance
    )

    # Buscar lista de usuários da escola para o filtro (Admins e Instrutores)
    users_escola = UserService.get_users_by_school(school_id)

    return render_template(
        'ferramentas/logs_admin.html',
        logs=logs,
        users=users_escola,
        data_inicio=data_inicio.strftime('%Y-%m-%d'),
        data_fim=data_fim.strftime('%Y-%m-%d'),
        filtro_user_id=filtro_user_id
    )