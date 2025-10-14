from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from backend.models.database import db
from backend.models.school import School
from backend.models.user import User
from utils.decorators import admin_or_programmer_required
from ..services.user_service import UserService

admin_escola_bp = Blueprint('admin_escola', __name__, url_prefix='/admin-escola')

@admin_escola_bp.route('/pre-cadastro', methods=['GET', 'POST'])
@login_required
@admin_or_programmer_required
def pre_cadastro():
    if request.method == 'POST':
        id_funcs_raw = request.form.get('id_funcs')
        role = request.form.get('role')
        school_id = request.form.get('school_id') # Usado pelo Super Admin

        # --- LÓGICA DE VINCULAÇÃO AUTOMÁTICA ---
        # Se o usuário logado for um admin de escola, usa a escola dele.
        if current_user.role == 'admin_escola':
            if current_user.user_schools:
                school_id = current_user.user_schools[0].school_id
            else:
                flash('Você não está associado a nenhuma escola para realizar o pré-cadastro.', 'danger')
                return redirect(url_for('main.dashboard'))
        # --- FIM DA LÓGICA ---
        
        # Validações
        if not id_funcs_raw or not role or not school_id:
            flash('Por favor, preencha todos os campos, incluindo a escola.', 'danger')
            return redirect(url_for('admin_escola.pre_cadastro'))

        id_funcs = [m.strip() for m in id_funcs_raw.replace(',', ' ').replace(';', ' ').split() if m.strip()]
        
        # Passa o school_id para o serviço de pré-cadastro em lote
        success, new_users_count, existing_users_count = UserService.batch_pre_register_users(id_funcs, role, school_id)
        
        if success:
            if new_users_count > 0:
                flash(f'{new_users_count} novo(s) usuário(s) pré-cadastrado(s) com sucesso na escola correta!', 'success')
            if existing_users_count > 0:
                flash(f'{existing_users_count} identificador(es) já existia(m) e foram ignorado(s).', 'info')
        else:
            flash(f'Erro ao pré-cadastrar usuários.', 'danger')

        return redirect(url_for('main.dashboard'))

    # Para a requisição GET, busca as escolas para o super admin selecionar
    schools = db.session.query(School).order_by(School.nome).all()
    return render_template('pre_cadastro.html', schools=schools)