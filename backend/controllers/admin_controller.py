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
from backend.models.aluno import Aluno
from backend.services.user_service import UserService
from sqlalchemy.orm import joinedload

import calendar
from datetime import date, datetime

admin_escola_bp = Blueprint('admin_escola', __name__, url_prefix='/admin/escola')

@admin_escola_bp.before_request
@login_required
def check_admin_permission():
    cargos_permitidos = ['admin', 'admin_escola', 'super_admin', 'programador']
    if not current_user.is_authenticated or current_user.role not in cargos_permitidos:
         flash('Acesso não autorizado.', 'danger')
         return redirect(url_for('main.index'))

# --- ROTAS DE UTILIDADE ---
@admin_escola_bp.route('/fix-banco-agora')
def fix_banco_agora():
    try:
        from backend.models.diario_classe import DiarioClasse
        from backend.models.frequencia import FrequenciaAluno
        db.create_all()
        return "<h1>Tabelas verificadas.</h1><a href='/'>Voltar</a>"
    except Exception as e:
        return f"<h1>Erro: {str(e)}</h1>"

# --- ROTAS DE GESTÃO (CRUD ADMINS) ---
@admin_escola_bp.route('/criar', methods=['GET', 'POST'])
def criar_admin():
    if not g.active_school: return redirect(url_for('main.index'))
    if request.method == 'POST':
        if db.session.query(User).filter((User.matricula == request.form.get('matricula')) | (User.email == request.form.get('email'))).first():
            flash('Usuário já existe.', 'danger')
            return redirect(url_for('admin_escola.criar_admin'))
        new_admin = User(matricula=request.form.get('matricula'), username=request.form.get('username'), email=request.form.get('email'), role='admin', is_active=True)
        new_admin.set_password(request.form.get('password') or "Mudar@123") 
        db.session.add(new_admin)
        db.session.flush()
        db.session.add(UserSchool(user_id=new_admin.id, school_id=g.active_school.id))
        db.session.commit()
        flash('Criado com sucesso!', 'success')
        return redirect(url_for('admin_escola.listar_admins'))
    return render_template('criar_admin_escola.html')

@admin_escola_bp.route('/listar')
def listar_admins():
    if not g.active_school: return redirect(url_for('main.index'))
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
         db.session.query(UserSchool).filter_by(user_id=user.id, school_id=g.active_school.id).delete()
         db.session.commit()
         flash("Removido.", "success")
    return redirect(url_for('admin_escola.listar_admins'))

# --- CALENDÁRIO / ESPELHO ---

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

        for week in raw_weeks:
            new_week = []
            for day in week:
                day_info = {'day': day, 'status': None, 'class': ''}
                if day != 0:
                    data_loop = date(ano, mes, day)
                    if day in resumo_dias:
                        if resumo_dias[day]['tem_falta']:
                            day_info.update({'status': 'danger', 'class': 'bg-light-danger border-danger'})
                        else:
                            day_info.update({'status': 'success', 'class': 'bg-light-success border-success'})
                    elif data_loop <= hoje:
                        day_info.update({'status': 'empty', 'class': 'bg-secondary text-white opacity-50'})
                    else:
                        day_info.update({'status': 'future', 'class': 'bg-light text-muted'})
                new_week.append(day_info)
            cal_data.append(new_week)

    # Navegação
    prev_m = mes - 1 if mes > 1 else 12
    prev_a = ano if mes > 1 else ano - 1
    next_m = mes + 1 if mes < 12 else 1
    next_a = ano if mes < 12 else ano + 1

    return render_template('admin/espelho_diarios.html', 
                           turmas=turmas, calendar_matrix=cal_data,
                           selected_turma=turma_id, mes=mes, ano=ano,
                           mes_nome=calendar.month_name[mes],
                           prev_m=prev_m, prev_a=prev_a, next_m=next_m, next_a=next_a)

@admin_escola_bp.route('/diarios/detalhes-ajax', methods=['GET'])
def detalhes_diario_ajax():
    turma_id = request.args.get('turma_id', type=int)
    dia = request.args.get('dia', type=int)
    mes = request.args.get('mes', type=int)
    ano = request.args.get('ano', type=int)

    if not all([turma_id, dia, mes, ano]): return "Erro parâmetros"

    data_alvo = date(ano, mes, dia)
    
    # Busca e ordena
    diarios = db.session.query(DiarioClasse).options(
        joinedload(DiarioClasse.disciplina),
        joinedload(DiarioClasse.responsavel)
    ).filter_by(
        turma_id=turma_id, data_aula=data_alvo
    ).all()

    # --- AGRUPAMENTO PARA VISUALIZAÇÃO ---
    # Transforma lista de registros em Cards Agrupados por Disciplina
    grupos = {}
    for d in diarios:
        if d.disciplina_id not in grupos:
            grupos[d.disciplina_id] = {
                'disciplina': d.disciplina,
                'responsavel': d.responsavel,
                'conteudo': d.conteudo_ministrado,
                'observacoes': d.observacoes,
                'qtd_registros': 0,
                'exemplo_id': d.id, # ID de referência para link de edição
                'tem_falta': False
            }
        
        grupos[d.disciplina_id]['qtd_registros'] += 1
        
        # Verifica se neste diário houve falta
        if any(not f.presente for f in d.frequencias):
            grupos[d.disciplina_id]['tem_falta'] = True

    return render_template('admin/partials/_detalhe_dia_modal.html', 
                           grupos=grupos.values(), 
                           data=data_alvo,
                           turma_id=turma_id)

# --- NOVA ROTA: EDITAR BLOCO DE DIÁRIOS (ADMIN) ---
@admin_escola_bp.route('/diarios/editar-bloco/<int:diario_ref_id>', methods=['GET', 'POST'])
def editar_diario_bloco(diario_ref_id):
    """Permite ao admin editar todos os diários de uma disciplina num dia específico."""
    
    # 1. Pega o diário de referência para saber data/turma/disciplina
    ref = db.session.get(DiarioClasse, diario_ref_id)
    if not ref:
        flash("Registro não encontrado.", "danger")
        return redirect(url_for('admin_escola.espelho_diarios'))

    # 2. Busca TODOS os diários desse bloco (mesma turma, data e disciplina)
    diarios_bloco = db.session.query(DiarioClasse).filter_by(
        turma_id=ref.turma_id,
        data_aula=ref.data_aula,
        disciplina_id=ref.disciplina_id
    ).all()

    turma = ref.turma
    alunos_turma = db.session.query(Aluno).filter_by(turma_id=turma.id).order_by(Aluno.num_aluno).all()

    if request.method == 'POST':
        try:
            # Atualiza dados gerais (conteúdo/obs) em TODOS os registros do bloco
            novo_conteudo = request.form.get('conteudo')
            nova_obs = request.form.get('observacoes')

            for diario in diarios_bloco:
                diario.conteudo_ministrado = novo_conteudo
                # Mantém prefixo de período na obs se existir, ou substitui tudo?
                # Vamos simplificar: Admin subscreve a observação geral.
                diario.observacoes = nova_obs
                
                # Atualiza frequências
                # Formato do name: presenca_{aluno_id}_{diario_id}
                for freq in diario.frequencias:
                    campo = f"presenca_{freq.aluno_id}_{diario.id}"
                    # Se marcado = 'on', presente = True.
                    esta_presente = request.form.get(campo) == 'on'
                    freq.presente = esta_presente
            
            db.session.commit()
            flash("Diário atualizado com sucesso!", "success")
            
            # Redireciona de volta para o calendário no mês correto
            return redirect(url_for('admin_escola.espelho_diarios', 
                                    turma_id=turma.id, 
                                    mes=ref.data_aula.month, 
                                    ano=ref.data_aula.year))

        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar: {str(e)}", "danger")

    return render_template('admin/editar_diario_bloco.html', 
                           diarios=diarios_bloco,
                           ref=ref,
                           alunos=alunos_turma)