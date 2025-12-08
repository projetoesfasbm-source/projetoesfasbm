# backend/controllers/admin_controller.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, g, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from backend.models.database import db
from backend.models.user import User
from backend.models.user_school import UserSchool
from backend.models.school import School
from backend.models.turma import Turma
from backend.services.email_service import EmailService
from backend.models.diario_classe import DiarioClasse

admin_escola_bp = Blueprint('admin_escola', __name__, url_prefix='/admin/escola')

@admin_escola_bp.before_request
@login_required
def check_admin_permission():
    """
    Verifica se o usuário logado é um Administrador de Escola ('admin').
    Caso contrário, redireciona para a página inicial.
    """
    if not current_user.is_authenticated or current_user.role != 'admin':
         flash('Acesso não autorizado.', 'danger')
         return redirect(url_for('main.index'))

@admin_escola_bp.route('/criar', methods=['GET', 'POST'])
def criar_admin():
    """
    Cria um novo usuário Administrador para a Escola ATIVA (g.active_school).
    """
    if not g.active_school:
        flash("Nenhuma escola ativa selecionada para vincular o administrador.", "warning")
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        matricula = request.form.get('matricula')
        username = request.form.get('username') # Nome de Guerra
        email = request.form.get('email')
        password = request.form.get('password') # Opcional
        
        # Validar duplicidade básica
        if db.session.query(User).filter((User.matricula == matricula) | (User.email == email)).first():
            flash('Matrícula ou Email já cadastrado.', 'danger')
            return redirect(url_for('admin_escola.criar_admin'))

        # Criar User
        new_admin = User(
            matricula=matricula,
            username=username, # Nome de Guerra
            email=email,
            role='admin',
            is_active=True 
        )
        if password:
            new_admin.set_password(password)
        else:
             # Senha padrão se não fornecida
             new_admin.set_password("Mudar@123") 

        db.session.add(new_admin)
        db.session.flush() # Para ter o ID

        # Vincular à Escola Ativa
        link = UserSchool(user_id=new_admin.id, school_id=g.active_school.id)
        db.session.add(link)

        db.session.commit()
        
        flash(f'Administrador {username} criado com sucesso para a escola {g.active_school.nome}!', 'success')
        return redirect(url_for('admin_escola.listar_admins'))

    return render_template('criar_admin_escola.html')

@admin_escola_bp.route('/listar')
def listar_admins():
    if not g.active_school:
        flash("Selecione uma escola.", "warning")
        return redirect(url_for('main.index'))

    # Buscar users que são 'admin' e têm vínculo com a escola ativa
    admins = db.session.query(User).join(UserSchool).filter(
        UserSchool.school_id == g.active_school.id,
        User.role == 'admin'
    ).all()

    return render_template('listar_admins_escola.html', admins=admins)

@admin_escola_bp.route('/editar/<int:user_id>', methods=['GET', 'POST'])
def editar_admin(user_id):
    # Verificar se o user pertence à escola ativa
    user = db.session.get(User, user_id)
    if not user:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for('admin_escola.listar_admins'))
    
    # Verificar vinculo
    link = db.session.query(UserSchool).filter_by(user_id=user.id, school_id=g.active_school.id).first()
    if not link:
        flash("Este usuário não pertence à escola ativa.", "danger")
        return redirect(url_for('admin_escola.listar_admins'))

    if request.method == 'POST':
        user.username = request.form.get('username')
        user.email = request.form.get('email')
        
        new_pass = request.form.get('password')
        if new_pass:
            user.set_password(new_pass)

        db.session.commit()
        flash("Dados atualizados.", "success")
        return redirect(url_for('admin_escola.listar_admins'))

    return render_template('criar_admin_escola.html', user=user, edit_mode=True)

@admin_escola_bp.route('/remover/<int:user_id>', methods=['POST'])
def remover_admin(user_id):
    user = db.session.get(User, user_id)
    if user:
         link = db.session.query(UserSchool).filter_by(user_id=user.id, school_id=g.active_school.id).first()
         if link:
             db.session.delete(link)
             db.session.commit()
             flash("Vínculo removido.", "success")
    return redirect(url_for('admin_escola.listar_admins'))

# --- ROTA PARA O ESPELHO DO DIÁRIO ---
@admin_escola_bp.route('/diarios/espelho', methods=['GET'])
def espelho_diarios():
    # Filtros via Query String (GET)
    turma_id = request.args.get('turma_id', type=int)
    data_filtro = request.args.get('data')
    
    diarios = []
    
    # Se filtros foram preenchidos, busca os dados
    if turma_id and data_filtro:
        diarios = db.session.query(DiarioClasse).filter_by(
            turma_id=turma_id, 
            data_aula=data_filtro
        ).all()
    
    # Lista turmas da escola ativa para preencher o select
    turmas = db.session.query(Turma).filter_by(school_id=g.active_school.id).all()
    
    return render_template('admin/espelho_diarios.html', 
                           diarios=diarios, 
                           turmas=turmas,
                           selected_turma=turma_id,
                           selected_data=data_filtro)