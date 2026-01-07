# backend/controllers/admin_controller.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from flask_login import login_required, current_user
from sqlalchemy import select, func, case, desc, and_
from sqlalchemy.orm import joinedload
from collections import defaultdict
from datetime import datetime
from functools import wraps

from backend.models.database import db
from backend.models.school import School
from backend.models.turma import Turma
from backend.models.aluno import Aluno
from backend.models.disciplina import Disciplina
from backend.models.diario_classe import DiarioClasse
from backend.models.frequencia import FrequenciaAluno
from backend.models.user import User
from backend.models.instrutor import Instrutor
from backend.services.user_service import UserService

admin_escola_bp = Blueprint('admin_escola', __name__, url_prefix='/admin-escola')

def sens_permission_required(f):
    """
    Decorator para permitir acesso ao SENS e Administradores no contexto da escola atual.
    Substitui a verificação global 'current_user.is_sens' para evitar vazamento de permissão entre escolas.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        # 1. Identifica a escola atual
        school_id = UserService.get_current_school_id()
        
        # 2. Verifica permissão ESPECÍFICA para esta escola
        # Aceita: SENS da escola, Admin da escola, Programador ou Super Admin
        if not (current_user.is_sens_in_school(school_id) or 
                current_user.is_admin_escola_in_school(school_id) or
                current_user.is_programador or 
                getattr(current_user, 'is_super_admin', False)):
            
            flash("Acesso restrito. Área exclusiva para a Seção de Ensino (SENS) nesta escola.", "danger")
            return redirect(url_for('main.dashboard'))
            
        return f(*args, **kwargs)
    return decorated_function

@admin_escola_bp.route('/')
@login_required
@sens_permission_required
def index():
    school_id = UserService.get_current_school_id()
    school = db.session.get(School, school_id)
    return render_template('admin/dashboard.html', school=school)

@admin_escola_bp.route('/espelho-diarios')
@login_required
@sens_permission_required
def espelho_diarios():
    school_id = UserService.get_current_school_id()
    if not school_id:
        flash("Escola não encontrada.", "danger")
        return redirect(url_for('main.dashboard'))

    # =========================================================================
    # PARTE 1: LÓGICA DO PAINEL DE RISCO
    # =========================================================================
    stats_query = db.session.execute(
        select(
            Aluno,
            Turma.nome.label('turma_nome'),
            Disciplina.materia,
            Disciplina.carga_horaria_prevista,
            func.count(FrequenciaAluno.id).label('total_faltas_materia')
        )
        .join(Turma, Aluno.turma_id == Turma.id)
        .join(FrequenciaAluno, Aluno.id == FrequenciaAluno.aluno_id)
        .join(DiarioClasse, FrequenciaAluno.diario_id == DiarioClasse.id)
        .join(Disciplina, DiarioClasse.disciplina_id == Disciplina.id)
        .options(joinedload(Aluno.user)) 
        .where(
            Turma.school_id == school_id,
            FrequenciaAluno.presente == False
        )
        .group_by(Aluno.id, Turma.nome, Disciplina.id)
    ).all()

    alunos_map = defaultdict(lambda: {
        'obj': None, 
        'turma': '', 
        'total_global_faltas': 0, 
        'disciplinas_risco': [],
        'max_gravidade': 0
    })

    for row in stats_query:
        aluno = row[0]
        turma_nome = row[1]
        materia = row[2]
        carga_total = row[3] or 1 
        faltas = row[4]

        porcentagem = (faltas / carga_total) * 100
        
        status_materia = 'normal'
        nivel_gravidade = 0
        if porcentagem >= 30:
            status_materia = 'reprovado'
            nivel_gravidade = 2
        elif porcentagem >= 20: 
            status_materia = 'alerta'
            nivel_gravidade = 1
        
        data = alunos_map[aluno.id]
        if not data['obj']:
            data['obj'] = aluno
            data['turma'] = turma_nome
        
        data['total_global_faltas'] += faltas
        
        if status_materia in ['reprovado', 'alerta']:
            data['disciplinas_risco'].append({
                'materia': materia,
                'faltas': faltas,
                'limite': int(carga_total * 0.3), 
                'porcentagem': round(porcentagem, 1),
                'status': status_materia
            })
            if nivel_gravidade > data['max_gravidade']:
                data['max_gravidade'] = nivel_gravidade

    alunos_alertas = []
    for uid, data in alunos_map.items():
        if data['disciplinas_risco'] or data['total_global_faltas'] >= 5:
            gravidade_str = 'moderado'
            if data['max_gravidade'] == 2: gravidade_str = 'critico'
            elif data['max_gravidade'] == 1: gravidade_str = 'atencao'
            
            aluno_obj = data['obj']
            nome_display = "Sem Nome"
            matricula_display = "N/D"
            if aluno_obj.user:
                nome_display = aluno_obj.user.nome_completo or aluno_obj.user.nome_de_guerra or "Sem Nome"
                matricula_display = aluno_obj.user.matricula or "N/D"

            alunos_alertas.append({
                'id': aluno_obj.id,
                'nome': nome_display,
                'matricula': matricula_display,
                'turma': data['turma'],
                'foto': aluno_obj.foto_perfil,
                'total_faltas': data['total_global_faltas'],
                'riscos': data['disciplinas_risco'], 
                'gravidade': gravidade_str
            })

    alunos_alertas.sort(key=lambda x: (
        {'critico': 0, 'atencao': 1, 'moderado': 2}[x['gravidade']], 
        -x['total_faltas']
    ))

    # =========================================================================
    # PARTE 2: LÓGICA DA LISTA DE DIÁRIOS
    # =========================================================================
    page = request.args.get('page', 1, type=int)
    turma_id = request.args.get('turma_id', type=int)
    data_str = request.args.get('data')

    # Query base para listar os diários
    query = select(DiarioClasse).join(Turma).where(Turma.school_id == school_id)

    if turma_id:
        query = query.where(DiarioClasse.turma_id == turma_id)
    
    if data_str:
        try:
            data_filtro = datetime.strptime(data_str, '%Y-%m-%d').date()
            query = query.where(DiarioClasse.data_aula == data_filtro)
        except ValueError:
            pass

    # Ordenação por Data e ID
    query = query.order_by(DiarioClasse.data_aula.desc(), DiarioClasse.id.desc())
    
    pagination = db.paginate(query, page=page, per_page=20)
    diarios_lista = pagination.items
    
    # Carregar turmas para o filtro
    turmas = db.session.scalars(select(Turma).where(Turma.school_id == school_id)).all()

    # Dados para a tabela de "Todos os Alunos" do modal/collapse
    todos_alunos_query = db.session.execute(
        select(Aluno, Turma.nome)
        .join(Turma)
        .join(User, Aluno.user_id == User.id)
        .where(Turma.school_id == school_id)
        .order_by(Turma.nome, User.nome_completo)
    ).all()

    todos_alunos_json = []
    for row in todos_alunos_query:
        a, t_nome = row
        nome_display = "Sem Nome"
        matricula_display = "N/D"
        if a.user:
             nome_display = a.user.nome_completo or a.user.nome_de_guerra or "Sem Nome"
             matricula_display = a.user.matricula or "N/D"

        todos_alunos_json.append({
            'id': a.id,
            'nome': nome_display,
            'matricula': matricula_display,
            'turma': t_nome,
            'faltas': alunos_map[a.id]['total_global_faltas'] if a.id in alunos_map else 0
        })

    return render_template(
        'admin/espelho_diarios.html', 
        alunos_alertas=alunos_alertas,
        todos_alunos=todos_alunos_json,
        diarios=diarios_lista,
        pagination=pagination,
        turmas=turmas
    )

@admin_escola_bp.route('/detalhe-faltas/<int:aluno_id>')
@login_required
@sens_permission_required
def detalhe_faltas_aluno(aluno_id):
    aluno = db.session.scalar(
        select(Aluno)
        .options(joinedload(Aluno.user), joinedload(Aluno.turma))
        .where(Aluno.id == aluno_id)
    )
    if not aluno:
        return "Aluno não encontrado", 404

    # Busca todas as faltas (ordenadas por disciplina e data)
    faltas_query = db.session.scalars(
        select(FrequenciaAluno)
        .join(DiarioClasse)
        .join(Disciplina)
        .where(FrequenciaAluno.aluno_id == aluno_id, FrequenciaAluno.presente == False)
        .order_by(Disciplina.materia, DiarioClasse.data_aula.desc())
    ).all()
    
    disciplinas_map = {}
    for f in faltas_query:
        disc = f.diario.disciplina
        if disc.id not in disciplinas_map:
            disciplinas_map[disc.id] = {
                'nome': disc.materia,
                'carga_horaria': disc.carga_horaria_prevista or 1,
                'total_faltas': 0,
                'dias': []
            }
        
        disciplinas_map[disc.id]['total_faltas'] += 1
        disciplinas_map[disc.id]['dias'].append({
            'data': f.diario.data_aula.strftime('%d/%m/%Y'),
            'justificativa': f.justificativa or "Sem justificativa",
            'id': f.id
        })

    resumo_final = []
    for d_id, data in disciplinas_map.items():
        percentual = (data['total_faltas'] / data['carga_horaria']) * 100
        status = 'success'
        if percentual >= 30: status = 'danger'
        elif percentual >= 20: status = 'warning'
        
        resumo_final.append({
            'disciplina': data['nome'],
            'total_faltas': data['total_faltas'],
            'limite_reprovacao': int(data['carga_horaria'] * 0.3),
            'percentual': round(percentual, 1),
            'status': status,
            'dias': data['dias']
        })
    
    resumo_final.sort(key=lambda x: x['percentual'], reverse=True)
    return render_template('admin/partials/_detalhe_dia_modal.html', aluno=aluno, resumo=resumo_final)

@admin_escola_bp.route('/editar-diario-bloco/<int:diario_id>', methods=['GET', 'POST'])
@login_required
@sens_permission_required
def editar_diario_bloco(diario_id):
    """
    Permite editar um bloco de aulas (mesma turma, data e disciplina).
    """
    ref_diario = db.session.get(DiarioClasse, diario_id)
    if not ref_diario:
        flash('Diário não encontrado', 'danger')
        return redirect(url_for('admin_escola.espelho_diarios'))

    # Busca todos os tempos da mesma aula no mesmo dia
    diarios_bloco = db.session.scalars(
        select(DiarioClasse)
        .where(
            DiarioClasse.turma_id == ref_diario.turma_id,
            DiarioClasse.disciplina_id == ref_diario.disciplina_id,
            DiarioClasse.data_aula == ref_diario.data_aula
        )
        .order_by(DiarioClasse.periodo, DiarioClasse.id) 
    ).all()

    # Busca alunos da turma ordenados
    alunos = db.session.scalars(
        select(Aluno)
        .join(User)
        .where(Aluno.turma_id == ref_diario.turma_id)
        .order_by(Aluno.num_aluno, User.nome_de_guerra)
    ).all()

    if request.method == 'POST':
        conteudo = request.form.get('conteudo')
        observacoes = request.form.get('observacoes')

        try:
            for diario in diarios_bloco:
                diario.conteudo_ministrado = conteudo
                diario.observacoes = observacoes
                
                # Atualiza Presenças
                for aluno in alunos:
                    campo_name = f"presenca_{aluno.id}_{diario.id}"
                    esta_presente = (request.form.get(campo_name) == 'on')

                    freq = db.session.scalar(
                        select(FrequenciaAluno).where(
                            FrequenciaAluno.diario_id == diario.id,
                            FrequenciaAluno.aluno_id == aluno.id
                        )
                    )

                    if not freq:
                        freq = FrequenciaAluno(diario_id=diario.id, aluno_id=aluno.id)
                        db.session.add(freq)
                    
                    freq.presente = esta_presente
                    if esta_presente:
                        freq.justificativa = None
            
            db.session.commit()
            flash('Diário de classe atualizado com sucesso!', 'success')
            return redirect(url_for('admin_escola.espelho_diarios'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao salvar: {str(e)}', 'danger')

    return render_template(
        'admin/editar_diario_bloco.html',
        ref=ref_diario,
        diarios=diarios_bloco,
        alunos=alunos
    )