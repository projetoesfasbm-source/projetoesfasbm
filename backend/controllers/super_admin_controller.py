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
from sqlalchemy import not_, select

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
        # ### INÍCIO DA ALTERAÇÃO ###
        # Capturamos o 'npccal_type' do formulário
        school_name = request.form.get('school_name')
        npccal_type = request.form.get('npccal_type')

        # Verificamos ambos os campos
        if not school_name or not npccal_type:
            flash('O nome da escola e o Tipo de NPCCAL são obrigatórios.', 'danger')
        else:
            # Enviamos ambos os dados para o service
            success, message = SchoolService.create_school(school_name, npccal_type)
            if success:
                flash(message, 'success')
            else:
                flash(message, 'danger')
        # ### FIM DA ALTERAÇÃO ###
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
    school_id_filter = request.args.get('school_id', type=int)
    role_filter = request.args.get('filter')

    if request.method == 'POST':
        action = request.form.get('action')
        user_id = request.form.get('user_id')
        school_id_form = request.form.get('school_id')
        
        if action == 'assign':
            role = request.form.get('role')
            success, message = UserService.assign_school_role(int(user_id), int(school_id_form), role)
            flash(message, 'success' if success else 'danger')
        elif action == 'remove':
            success, message = UserService.remove_school_role(int(user_id), int(school_id_form))
            flash(message, 'success' if success else 'danger')
        
        return redirect(url_for('super_admin.manage_assignments', school_id=school_id_filter, filter=role_filter))

    # Query base para todos os usuários gerenciáveis
    all_manageable_users_query = db.select(User).filter(
        User.role.notin_(['programador', 'super_admin'])
    ).order_by(User.nome_completo)
    all_manageable_users = db.session.scalars(all_manageable_users_query).all()

    # Queries de atribuição e órfãos
    assignments = []
    orphans = []

    if role_filter == 'orphans':
        assigned_user_ids = db.session.scalars(db.select(UserSchool.user_id).distinct()).all()
        orphans_query = db.select(User).where(
            User.id.notin_(assigned_user_ids),
            User.role.notin_(['programador', 'super_admin'])
        )
        orphans = db.session.scalars(orphans_query).all()
    else:
        assignments_query = db.select(UserSchool).join(User).join(School)
        if school_id_filter:
            assignments_query = assignments_query.where(UserSchool.school_id == school_id_filter)
        
        if role_filter in ['admin_escola', 'instrutor', 'aluno']:
            assignments_query = assignments_query.where(UserSchool.role == role_filter)
        elif role_filter == 'preregistered':
            assignments_query = assignments_query.where(User.is_active == False)
        
        assignments = db.session.scalars(assignments_query.order_by(User.nome_completo)).all()
    
    schools = db.session.scalars(db.select(School).order_by(School.nome)).all()

    return render_template(
        'super_admin/manage_assignments.html', 
        users=all_manageable_users, 
        schools=schools, 
        assignments=assignments,
        orphans=orphans,
        selected_school_id=school_id_filter,
        selected_filter=role_filter
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
    school_id_filter = request.args.get('school_id', type=int)
    role_filter = request.args.get('filter')
    success, message = UserService.delete_user_by_id(user_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('super_admin.manage_assignments', school_id=school_id_filter, filter=role_filter))

@super_admin_bp.route('/reset-user-password', methods=['POST'])
@login_required
@super_admin_required
def reset_user_password():
    school_id_filter = request.args.get('school_id', type=int)
    role_filter = request.args.get('filter')
    user_id = request.form.get('user_id')
    if not user_id:
        flash('Nenhum usuário selecionado.', 'danger')
        return redirect(url_for('super_admin.manage_assignments', school_id=school_id_filter, filter=role_filter))

    user = db.session.get(User, int(user_id))
    if not user:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('super_admin.manage_assignments', school_id=school_id_filter, filter=role_filter))
    
    if user.role in ['super_admin', 'programador']:
        flash('Não é permitido resetar a senha de um Super Admin ou Programador por este método.', 'warning')
        return redirect(url_for('super_admin.manage_assignments', school_id=school_id_filter, filter=role_filter))

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

    return redirect(url_for('super_admin.manage_assignments', school_id=school_id_filter, filter=role_filter))

@super_admin_bp.route('/select-school')
@login_required
@super_admin_required
def select_school():
    """Página para o Super Admin selecionar a escola ativa."""
    schools = db.session.scalars(select(School).order_by(School.nome)).all()
    return render_template('select_school.html', schools=schools)


@super_admin_bp.route('/set-active-school/<int:school_id>')
@login_required
@super_admin_required
def set_active_school(school_id):
    """Define a escola ativa para o Super Admin na sessão."""
    school = db.session.get(School, school_id)
    if school:
        session['view_as_school_id'] = school.id
        session['view_as_school_name'] = school.nome
        flash(f'Visualizando como administrador da escola {school.nome}.', 'success')
    else:
        flash('Escola não encontrada.', 'danger')
    
    return redirect(url_for('main.dashboard'))