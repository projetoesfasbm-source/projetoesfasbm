# backend/controllers/super_admin_controller.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from flask_login import login_required, current_user, login_user
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
    # --- FAXINA DE ESTADO ---
    # Se o Super Admin entrou no Painel Global, garantimos que ele 
    # não está "preso" a nenhuma escola de visualizações anteriores.
    session.pop('view_as_school_id', None)
    session.pop('view_as_school_name', None)
    session.pop('active_school_id', None)
    # ------------------------

    all_schools = db.session.query(School).order_by(School.nome).all()
    return render_template('super_admin/dashboard.html', all_schools=all_schools)

@super_admin_bp.route('/clear-school-selection')
@login_required
@super_admin_required
def clear_school_selection():
    """Remove a escola ativa da sessão e devolve o Super Admin para o Painel Global (DEC)"""
    session.pop('view_as_school_id', None)
    session.pop('view_as_school_name', None)
    session.pop('active_school_id', None) # Garante a limpeza total da sessão
    
    flash('Você retornou ao Painel Global (Modo DEC).', 'info')
    return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/schools', methods=['GET', 'POST'])
@login_required
@super_admin_required
def manage_schools():
    if request.method == 'POST':
        school_name = request.form.get('school_name')
        npccal_type = request.form.get('npccal_type')

        if not school_name or not npccal_type:
            flash('O nome da escola e o Tipo de NPCCAL são obrigatórios.', 'danger')
        else:
            success, message = SchoolService.create_school(school_name, npccal_type)
            if success:
                flash(message, 'success')
            else:
                flash(message, 'danger')
        return redirect(url_for('super_admin.manage_schools'))
        
    schools = db.session.query(School).order_by(School.nome).all()
    return render_template('super_admin/manage_schools.html', schools=schools)

@super_admin_bp.route('/schools/edit/<int:school_id>', methods=['POST'])
@login_required
@super_admin_required
def edit_school(school_id):
    school_name = request.form.get('school_name')
    npccal_type = request.form.get('npccal_type')

    success, message = SchoolService.update_school(school_id, school_name, npccal_type)
    
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('super_admin.manage_schools'))

@super_admin_bp.route('/schools/delete/<int:school_id>', methods=['POST'])
@login_required
@super_admin_required
def delete_school(school_id):
    password = request.form.get('password')
    
    if not password:
        flash('A senha é obrigatória para confirmar a exclusão.', 'danger')
        return redirect(url_for('super_admin.manage_schools'))

    # Passa o current_user e a senha para o Service validar
    success, message = SchoolService.delete_school(school_id, current_user, password)
    
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
        session['active_school_id'] = school.id # Injeta para que os menus funcionem perfeitamente
        flash(f'Você entrou no modo de intervenção da escola: {school.nome}.', 'success')
    else:
        flash('Escola não encontrada.', 'danger')
    
    return redirect(url_for('main.dashboard'))

# --- GESTÃO DE ACESSOS DEC (SUPER ADMINS) ---
@super_admin_bp.route('/gestores-dec', methods=['GET', 'POST'])
@login_required
@super_admin_required
def manage_gestores():
    if request.method == 'POST':
        action = request.form.get('action')
        
        # --- PROMOVER USUÁRIO ---
        if action == 'add':
            matricula = request.form.get('matricula')
            # Importação local para evitar erro circular
            from utils.normalizer import normalize_matricula
            mat_norm = normalize_matricula(matricula)
            
            user = db.session.execute(select(User).where(User.matricula == mat_norm)).scalar_one_or_none()
            if user:
                if user.role == 'super_admin':
                    flash(f'O usuário {user.nome_de_guerra or user.nome_completo} já é um Gestor DEC.', 'warning')
                else:
                    user.role = 'super_admin'
                    db.session.commit()
                    flash(f'{user.nome_de_guerra or user.nome_completo} foi promovido a Gestor DEC com sucesso!', 'success')
            else:
                flash('Nenhum usuário encontrado com essa matrícula.', 'danger')
                
        # --- REBAIXAR USUÁRIO ---
        elif action == 'remove':
            user_id = request.form.get('user_id')
            user = db.session.get(User, int(user_id))
            
            if user:
                if user.id == current_user.id:
                    flash('Você não pode remover seus próprios privilégios por aqui. Isso evita que o sistema fique sem administrador.', 'danger')
                else:
                    user.role = 'instrutor' # Rebaixa para instrutor por padrão
                    db.session.commit()
                    flash(f'Privilégios de Gestor DEC removidos de {user.nome_de_guerra or user.nome_completo}.', 'info')
                    
        return redirect(url_for('super_admin.manage_gestores'))
        
    gestores = db.session.scalars(select(User).where(User.role == 'super_admin').order_by(User.nome_completo)).all()
    
    return render_template('super_admin/gestores_dec.html', gestores=gestores)


# =========================================================================
# LÓGICA DE PERSONIFICAÇÃO ("LOGAR COMO")
# =========================================================================

@super_admin_bp.route('/logar-como/<int:user_id>')
@login_required
def logar_como(user_id):
    """ Coloca o disfarce e assume o controle da conta alvo """
    
    if current_user.role != 'super_admin':
        flash("Acesso negado.", "danger")
        return redirect(url_for('main.dashboard'))

    alvo = db.session.get(User, user_id)
    if not alvo:
        flash("Usuário alvo não encontrado.", "danger")
        return redirect(request.referrer or url_for('super_admin.dashboard'))

    # 1. Guarda o seu ID original e a ESCOLA ATUAL antes de trocar de roupa
    admin_id = current_user.id
    escola_id = session.get('view_as_school_id') or session.get('active_school_id')
    escola_nome = session.get('view_as_school_name')
    
    # 2. Faz o login forçado (sem senha)
    login_user(alvo)
    
    # 3. Salva o rastro na memória (DEPOIS do login para não ser apagado)
    session['impersonator_id'] = admin_id
    if escola_id:
        session['impersonator_return_school_id'] = escola_id
    if escola_nome:
        session['impersonator_return_school_name'] = escola_nome

    # Limpa a visão do DEC para o disfarce ser perfeito
    session.pop('is_dec_mode', None)
    session.pop('active_school_id', None)
    session.pop('view_as_school_id', None)
    session.pop('view_as_school_name', None)
    
    flash(f"Modo Espião: Você assumiu a conta de {alvo.nome_completo or alvo.username}.", "warning")
    return redirect(url_for('main.selecionar_escola'))


@super_admin_bp.route('/voltar-admin')
@login_required
def voltar_admin():
    """ Tira o disfarce e devolve para a Escola ou Painel do DEC """
    
    admin_id = session.get('impersonator_id')
    if not admin_id:
        flash("Nenhum disfarce ativo encontrado.", "danger")
        return redirect(url_for('main.dashboard'))

    admin_user = db.session.get(User, admin_id)
    if admin_user:
        # Recupera as coordenadas da escola antes de limpar o disfarce
        retorno_escola_id = session.get('impersonator_return_school_id')
        retorno_escola_nome = session.get('impersonator_return_school_name')

        # 1. Faz o login de volta como Super Admin
        login_user(admin_user)
        
        # 2. Limpa o lixo da personificação
        session.pop('impersonator_id', None)
        session.pop('impersonator_return_school_id', None)
        session.pop('impersonator_return_school_name', None)
        
        # 3. Devolve o chapéu do DEC
        session['is_dec_mode'] = True
        
        # 4. O RETORNO ESCALONADO: Se tinha uma escola salva, volta para ela!
        if retorno_escola_id:
            session['view_as_school_id'] = retorno_escola_id
            session['active_school_id'] = retorno_escola_id
            if retorno_escola_nome:
                session['view_as_school_name'] = retorno_escola_nome
            
            flash("Disfarce removido. Você retornou à gestão da escola.", "success")
            return redirect(url_for('main.dashboard'))
        else:
            flash("Disfarce removido. Controle Super Admin restaurado.", "success")
            return redirect(url_for('super_admin.dashboard'))
        
    return redirect(url_for('auth.logout'))