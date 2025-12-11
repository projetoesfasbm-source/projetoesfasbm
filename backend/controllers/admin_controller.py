# backend/controllers/admin_controller.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from sqlalchemy import select, func, case, desc
from collections import defaultdict

from backend.models.database import db
from backend.models.school import School
from backend.models.turma import Turma
from backend.models.aluno import Aluno
from backend.models.disciplina import Disciplina
from backend.models.diario_classe import DiarioClasse
from backend.models.frequencia import FrequenciaAluno
from backend.services.user_service import UserService
from utils.decorators import admin_escola_required

admin_escola_bp = Blueprint('admin_escola', __name__, url_prefix='/admin-escola')

@admin_escola_bp.route('/')
@login_required
@admin_escola_required
def index():
    school_id = UserService.get_current_school_id()
    school = db.session.get(School, school_id)
    return render_template('admin/dashboard.html', school=school)

@admin_escola_bp.route('/espelho-diarios')
@login_required
@admin_escola_required
def espelho_diarios():
    school_id = UserService.get_current_school_id()
    if not school_id:
        flash("Escola não encontrada.", "danger")
        return redirect(url_for('main.dashboard'))

    # 1. Busca estatísticas detalhadas de faltas por Disciplina
    # Agrupa por Aluno e Disciplina para calcular a % específica
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
        .where(
            Turma.school_id == school_id,
            FrequenciaAluno.presente == False
        )
        .group_by(Aluno.id, Turma.nome, Disciplina.id)
    ).all()

    # Dicionário para agregar dados por aluno
    alunos_map = defaultdict(lambda: {
        'obj': None, 
        'turma': '', 
        'total_global_faltas': 0, 
        'disciplinas_risco': [],
        'max_gravidade': 0 # 0: Ok, 1: Alerta, 2: Crítico/Reprovado
    })

    # Processa os dados
    for row in stats_query:
        aluno = row[0]
        turma_nome = row[1]
        materia = row[2]
        carga_total = row[3] or 1 # Evita divisão por zero
        faltas = row[4]

        # Calcula porcentagem de faltas nesta matéria
        porcentagem = (faltas / carga_total) * 100
        
        # Define status da matéria
        status_materia = 'normal'
        if porcentagem >= 30:
            status_materia = 'reprovado'
            nivel_gravidade = 2
        elif porcentagem >= 20: # Alerta se estiver perto (20% a 29%)
            status_materia = 'alerta'
            nivel_gravidade = 1
        else:
            nivel_gravidade = 0

        # Atualiza dados do aluno no mapa
        data = alunos_map[aluno.id]
        if not data['obj']:
            data['obj'] = aluno
            data['turma'] = turma_nome
        
        data['total_global_faltas'] += faltas
        
        # Se houver risco (Alerta ou Reprovado), adiciona à lista de destaque
        if status_materia in ['reprovado', 'alerta']:
            data['disciplinas_risco'].append({
                'materia': materia,
                'faltas': faltas,
                'limite': int(carga_total * 0.3), # Quantas faltas reprovam
                'porcentagem': round(porcentagem, 1),
                'status': status_materia
            })
            
            # Atualiza gravidade máxima do aluno (para ordenar cards depois)
            if nivel_gravidade > data['max_gravidade']:
                data['max_gravidade'] = nivel_gravidade

    # Transforma em lista e ordena: Reprovados primeiro, depois Alertas
    alunos_alertas = []
    for uid, data in alunos_map.items():
        # Só adiciona no painel de cards se tiver alguma matéria em risco ou muitas faltas globais
        if data['disciplinas_risco'] or data['total_global_faltas'] >= 5:
            gravidade_str = 'moderado'
            if data['max_gravidade'] == 2: gravidade_str = 'critico' # Reprovado
            elif data['max_gravidade'] == 1: gravidade_str = 'atencao' # Quase lá
            
            alunos_alertas.append({
                'id': data['obj'].id,
                'nome': data['obj'].nome_completo or data['obj'].nome_de_guerra,
                'matricula': data['obj'].matricula,
                'turma': data['turma'],
                'foto': data['obj'].foto_perfil,
                'total_faltas': data['total_global_faltas'],
                'riscos': data['disciplinas_risco'], # Lista de matérias com problema
                'gravidade': gravidade_str
            })

    # Ordena: Crítico -> Atenção -> Moderado -> Total de faltas
    alunos_alertas.sort(key=lambda x: (
        {'critico': 0, 'atencao': 1, 'moderado': 2}[x['gravidade']], 
        -x['total_faltas']
    ))

    # 2. Busca lista completa simples para a tabela de pesquisa geral (sem processamento pesado)
    todos_alunos_query = db.session.execute(
        select(Aluno, Turma.nome)
        .join(Turma)
        .where(Turma.school_id == school_id)
        .order_by(Turma.nome, Aluno.nome_completo)
    ).all()

    todos_alunos_json = []
    for row in todos_alunos_query:
        a, t_nome = row
        todos_alunos_json.append({
            'id': a.id,
            'nome': a.nome_completo or a.nome_de_guerra,
            'matricula': a.matricula,
            'turma': t_nome,
            # Se ele estiver na lista de alertas, pegamos as faltas de lá, senão 0
            'faltas': alunos_map[a.id]['total_global_faltas'] if a.id in alunos_map else 0
        })

    return render_template(
        'admin/espelho_diarios.html', 
        alunos_alertas=alunos_alertas,
        todos_alunos=todos_alunos_json
    )

@admin_escola_bp.route('/detalhe-faltas/<int:aluno_id>')
@login_required
@admin_escola_required
def detalhe_faltas_aluno(aluno_id):
    aluno = db.session.get(Aluno, aluno_id)
    if not aluno:
        return "Aluno não encontrado", 404

    # Busca faltas detalhadas
    faltas = db.session.scalars(
        select(FrequenciaAluno)
        .join(DiarioClasse) # Garante join
        .join(Disciplina)   # Garante join
        .where(
            FrequenciaAluno.aluno_id == aluno_id,
            FrequenciaAluno.presente == False
        )
        .order_by(FrequenciaAluno.diario_id.desc()) # Ordena por ID do diário (cronológico reverso aproximado)
    ).all()
    
    detalhes = []
    for f in faltas:
        # Acesso seguro às relações
        disciplina_nome = "N/D"
        data_aula = "N/D"
        
        if f.diario:
            data_aula = f.diario.data_aula.strftime('%d/%m/%Y')
            if f.diario.disciplina:
                disciplina_nome = f.diario.disciplina.materia
            
        detalhes.append({
            'data': data_aula,
            'disciplina': disciplina_nome,
            'observacao': f.observacao or ""
        })

    return render_template('admin/partials/_detalhe_dia_modal.html', aluno=aluno, faltas=detalhes)