# backend/controllers/admin_controller.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, g
from flask_login import login_required, current_user
from backend.models.database import db
from backend.models.user import User
from backend.models.user_school import UserSchool
from backend.models.school import School
from backend.models.turma import Turma
from backend.models.diario_classe import DiarioClasse
from backend.models.frequencia import FrequenciaAluno
from backend.services.user_service import UserService

import calendar
from datetime import date

admin_escola_bp = Blueprint('admin_escola', __name__, url_prefix='/admin/escola')

@admin_escola_bp.before_request
@login_required
def check_admin_permission():
    cargos_permitidos = ['admin', 'admin_escola', 'super_admin', 'programador']
    if not current_user.is_authenticated or current_user.role not in cargos_permitidos:
         flash('Acesso não autorizado.', 'danger')
         return redirect(url_for('main.index'))

# --- ROTA DE CORREÇÃO DO BANCO DE DADOS (CLIQUE NELA UMA VEZ) ---
@admin_escola_bp.route('/fix-banco-agora')
def fix_banco_agora():
    """
    Rota de emergência para criar as tabelas que estão faltando.
    Acesse: /admin/escola/fix-banco-agora
    """
    try:
        # Força a importação dos modelos
        from backend.models.diario_classe import DiarioClasse
        from backend.models.frequencia import FrequenciaAluno
        
        # Cria todas as tabelas que ainda não existem
        db.create_all()
        return "<h1>Sucesso! Tabelas criadas. Agora o Painel do Chefe deve funcionar.</h1><a href='/'>Voltar</a>"
    except Exception as e:
        return f"<h1>Erro: {str(e)}</h1>"

# --- DEMAIS ROTAS ---

@admin_escola_bp.route('/pre-cadastro', methods=['GET', 'POST'])
def pre_cadastro():
    if request.method == 'POST':
        id_funcs_raw = request.form.get('id_funcs')
        role = request.form.get('role')
        school_id = request.form.get('school_id') 

        if current_user.role == 'admin_escola' or current_user.role == 'admin':
            if hasattr(current_user, 'user_schools') and current_user.user_schools:
                school_id = current_user.user_schools[0].school_id
            elif g.active_school:
                school_id = g.active_school.id
            else:
                flash('Você não está associado a nenhuma escola.', 'danger')
                return redirect(url_for('main.dashboard'))
        
        if not id_funcs_raw or not role or not school_id:
            flash('Preencha todos os campos.', 'danger')
            return redirect(url_for('admin_escola.pre_cadastro'))

        id_funcs = [m.strip() for m in id_funcs_raw.replace(',', ' ').replace(';', ' ').split() if m.strip()]
        success, new_users, existing_users = UserService.batch_pre_register_users(id_funcs, role, school_id)
        
        if success:
            flash(f'{new_users} usuários pré-cadastrados. {existing_users} já existiam.', 'success')
        else:
            flash(f'Erro ao pré-cadastrar.', 'danger')

        return redirect(url_for('main.dashboard'))

    schools = db.session.query(School).order_by(School.nome).all()
    return render_template('pre_cadastro.html', schools=schools)

@admin_escola_bp.route('/criar', methods=['GET', 'POST'])
def criar_admin():
    if not g.active_school:
        flash("Nenhuma escola ativa.", "warning")
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        matricula = request.form.get('matricula')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if db.session.query(User).filter((User.matricula == matricula) | (User.email == email)).first():
            flash('Matrícula ou Email já cadastrado.', 'danger')
            return redirect(url_for('admin_escola.criar_admin'))

        new_admin = User(matricula=matricula, username=username, email=email, role='admin', is_active=True)
        new_admin.set_password(password if password else "Mudar@123") 

        db.session.add(new_admin)
        db.session.flush()
        db.session.add(UserSchool(user_id=new_admin.id, school_id=g.active_school.id))
        db.session.commit()
        
        flash(f'Administrador {username} criado!', 'success')
        return redirect(url_for('admin_escola.listar_admins'))

    return render_template('criar_admin_escola.html')

@admin_escola_bp.route('/listar')
def listar_admins():
    if not g.active_school:
        return redirect(url_for('main.index'))
    admins = db.session.query(User).join(UserSchool).filter(UserSchool.school_id == g.active_school.id, User.role == 'admin').all()
    return render_template('listar_admins_escola.html', admins=admins)

@admin_escola_bp.route('/editar/<int:user_id>', methods=['GET', 'POST'])
def editar_admin(user_id):
    user = db.session.get(User, user_id)
    if not user: return redirect(url_for('admin_escola.listar_admins'))
    
    if request.method == 'POST':
        user.username = request.form.get('username')
        user.email = request.form.get('email')
        if request.form.get('password'): user.set_password(request.form.get('password'))
        db.session.commit()
        flash("Atualizado.", "success")
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
             flash("Removido.", "success")
    return redirect(url_for('admin_escola.listar_admins'))

# --- ESPELHO DE DIÁRIOS (CALENDÁRIO) ---

@admin_escola_bp.route('/diarios/espelho', methods=['GET'])
def espelho_diarios():
    turmas = db.session.query(Turma).filter_by(school_id=g.active_school.id).all()
    turma_id = request.args.get('turma_id', type=int)
    
    hoje = date.today()
    try:
        mes = int(request.args.get('mes', hoje.month))
        ano = int(request.args.get('ano', hoje.year))
    except:
        mes, ano = hoje.month, hoje.year

    cal_data = [] 
    
    if turma_id:
        _, num_days = calendar.monthrange(ano, mes)
        start_date = date(ano, mes, 1)
        end_date = date(ano, mes, num_days)

        diarios_mes = db.session.query(DiarioClasse).filter(
            DiarioClasse.turma_id == turma_id,
            DiarioClasse.data_aula >= start_date,
            DiarioClasse.data_aula <= end_date
        ).all()

        resumo_dias = {}
        for diario in diarios_mes:
            dia = diario.data_aula.day
            if dia not in resumo_dias: resumo_dias[dia] = {'tem_falta': False}
            if any(not f.presente for f in diario.frequencias): resumo_dias[dia]['tem_falta'] = True

        cal = calendar.Calendar(firstweekday=6)
        raw_weeks = cal.monthdayscalendar(ano, mes)

        new_cal_data = []
        for week in raw_weeks:
            new_week = []
            for day in week:
                day_info = {'day': day, 'status': None, 'class': ''}
                if day != 0:
                    data_atual_loop = date(ano, mes, day)
                    
                    if day in resumo_dias:
                        if resumo_dias[day]['tem_falta']:
                            day_info['status'] = 'danger'
                            day_info['class'] = 'border-danger bg-light-danger text-danger'
                        else:
                            day_info['status'] = 'success'
                            day_info['class'] = 'border-success bg-light-success text-success'
                    else:
                        # Se for hoje ou passado e não tiver registro: EMPTY (Cinza)
                        if data_atual_loop <= hoje:
                             day_info['status'] = 'empty'
                             day_info['class'] = 'bg-secondary text-white opacity-50 border-secondary'
                        else:
                             day_info['status'] = 'future'
                             day_info['class'] = 'bg-light text-muted'

                new_week.append(day_info)
            new_cal_data.append(new_week)
        cal_data = new_cal_data

    # Navegação
    prev_mes = mes - 1 if mes > 1 else 12
    prev_ano = ano if mes > 1 else ano - 1
    next_mes = mes + 1 if mes < 12 else 1
    next_ano = ano if mes < 12 else ano + 1

    return render_template('admin/espelho_diarios.html', 
                           turmas=turmas, calendar_matrix=cal_data,
                           selected_turma=turma_id, mes=mes, ano=ano,
                           mes_nome=calendar.month_name[mes],
                           prev_m=prev_mes, prev_a=prev_ano,
                           next_m=next_mes, next_a=next_ano)

@admin_escola_bp.route('/diarios/detalhes-ajax', methods=['GET'])
def detalhes_diario_ajax():
    turma_id = request.args.get('turma_id', type=int)
    dia = request.args.get('dia', type=int)
    mes = request.args.get('mes', type=int)
    ano = request.args.get('ano', type=int)

    if not all([turma_id, dia, mes, ano]):
        return "<div class='alert alert-danger'>Erro nos parâmetros.</div>"

    data_alvo = date(ano, mes, dia)
    diarios = db.session.query(DiarioClasse).filter_by(turma_id=turma_id, data_aula=data_alvo).all()

    # Se não houver diários, passamos lista vazia para o template lidar (mostrar msg de vazio)
    return render_template('admin/partials/_detalhe_dia_modal.html', diarios=diarios, data=data_alvo)