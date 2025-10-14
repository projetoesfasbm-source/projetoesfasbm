# backend/controllers/super_admin_controller.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from flask_login import login_required
import secrets
import string
from utils.decorators import super_admin_required
from ..models.database import db
from ..models.school import School
from ..models.user import User
from ..models.user_school import UserSchool
from ..services.school_service import SchoolService
from ..services.user_service import UserService
from sqlalchemy import not_

super_admin_bp = Blueprint('super_admin', __name__, url_prefix='/super-admin')

@super_admin_bp.route('/dashboard', methods=['GET'])
@login_required
@super_admin_required
def dashboard():
    all_schools = db.session.query(School).order_by(School.nome).all()
    return render_template('super_admin/dashboard.html', all_schools=all_schools)

@super_admin_bp.route('/exit-view')
@login_required
@super_admin_required
def exit_view():
    session.pop('view_as_school_id', None)
    session.pop('view_as_school_name', None)
    flash('Você saiu do modo de visualização.', 'info')
    return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/schools', methods=['GET', 'POST'])
@login_required
@super_admin_required
def manage_schools():
    if request.method == 'POST':
        school_name = request.form.get('school_name')
        if not school_name:
            flash('O nome da escola é obrigatório.', 'danger')
        else:
            success, message = SchoolService.create_school(school_name)
            if success:
                flash(message, 'success')
            else:
                flash(message, 'danger')
        return redirect(url_for('super_admin.manage_schools'))
        
    schools = db.session.query(School).order_by(School.nome).all()
    return render_template('super_admin/manage_schools.html', schools=schools)

@super_admin_bp.route('/schools/delete/<int:school_id>', methods=['POST'])
@login_required
@super_admin_required
def delete_school(school_id):
    success, message = SchoolService.delete_school(school_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('super_admin.manage_schools'))

@super_admin_bp.route('/assignments', methods=['GET', 'POST'])
@login_required
@super_admin_required
def manage_assignments():
    if request.method == 'POST':
        action = request.form.get('action')
        user_id = request.form.get('user_id')
        school_id = request.form.get('school_id')
        
        if action == 'assign':
            role = request.form.get('role')
            success, message = UserService.assign_school_role(int(user_id), int(school_id), role)
            flash(message, 'success' if success else 'danger')
        elif action == 'remove':
            success, message = UserService.remove_school_role(int(user_id), int(school_id))
            flash(message, 'success' if success else 'danger')
        
        return redirect(url_for('super_admin.manage_assignments'))

    all_manageable_users_query = db.select(User).filter(
        User.role.notin_(['programador', 'super_admin'])
    ).order_by(User.nome_completo)
    all_manageable_users = db.session.scalars(all_manageable_users_query).all()

    assignments = db.session.scalars(db.select(UserSchool).join(User).join(School)).all()
    assigned_user_ids = {a.user_id for a in assignments}

    unassigned_users = [user for user in all_manageable_users if user.id not in assigned_user_ids]
    
    schools = db.session.scalars(db.select(School).order_by(School.nome)).all()

    return render_template(
        'super_admin/manage_assignments.html', 
        users=all_manageable_users, 
        schools=schools, 
        assignments=assignments,
        unassigned_users=unassigned_users
    )

@super_admin_bp.route('/create-administrator', methods=['POST'])
@login_required
@super_admin_required
def create_administrator():
    nome_completo = request.form.get('nome_completo')
    email = request.form.get('email')
    matricula = request.form.get('matricula')
    school_id = request.form.get('school_id')

    if not all([nome_completo, email, matricula, school_id]):
        flash('Todos os campos são obrigatórios.', 'danger')
        return redirect(url_for('super_admin.manage_schools'))

    existing_user = User.query.filter((User.email == email) | (User.matricula == matricula)).first()
    if existing_user:
        flash('Um usuário com este email ou Matrícula já existe.', 'danger')
        return redirect(url_for('super_admin.manage_schools'))

    alphabet = string.ascii_letters + string.digits
    temp_password = ''.join(secrets.choice(alphabet) for i in range(10))

    new_user = User(
        nome_completo=nome_completo,
        email=email,
        matricula=matricula,
        role='admin_escola',
        is_active=True,
        must_change_password=True
    )
    new_user.set_password(temp_password)
    
    db.session.add(new_user)
    db.session.flush()

    user_school = UserSchool(
        user_id=new_user.id,
        school_id=school_id,
        role='admin_escola'
    )
    db.session.add(user_school)
    
    try:
        db.session.commit()
        flash(f'Administrador "{nome_completo}" criado com sucesso! Senha temporária: {temp_password}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar administrador: {e}', 'danger')

    return redirect(url_for('super_admin.manage_schools'))

@super_admin_bp.route('/delete-user/<int:user_id>', methods=['POST'])
@login_required
@super_admin_required
def delete_user(user_id):
    success, message = UserService.delete_user_by_id(user_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('super_admin.manage_assignments'))

# --- NOVA ROTA PARA RESETAR SENHA ---
@super_admin_bp.route('/reset-user-password', methods=['POST'])
@login_required
@super_admin_required
def reset_user_password():
    user_id = request.form.get('user_id')
    if not user_id:
        flash('Nenhum usuário selecionado.', 'danger')
        return redirect(url_for('super_admin.manage_assignments'))

    user = db.session.get(User, int(user_id))
    if not user:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('super_admin.manage_assignments'))
    
    if user.role in ['super_admin', 'programador']:
        flash('Não é permitido resetar a senha de um Super Admin ou Programador por este método.', 'warning')
        return redirect(url_for('super_admin.manage_assignments'))

    # Gera senha temporária segura
    alphabet = string.ascii_letters + string.digits + '!@#$%^&*'
    temp_password = ''.join(secrets.choice(alphabet) for i in range(12))

    try:
        user.set_password(temp_password)
        user.must_change_password = True
        db.session.commit()
        flash(f'Senha para o usuário "{user.nome_completo or user.username}" resetada com sucesso! Nova senha temporária: {temp_password}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ocorreu um erro ao resetar a senha: {e}', 'danger')

    return redirect(url_for('super_admin.manage_assignments'))