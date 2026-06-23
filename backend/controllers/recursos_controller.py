# backend/controllers/recursos_controller.py

import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, session, g
from flask_login import login_required, current_user
from backend.models.database import db
from backend.models.recurso import ProvaRecurso, Recurso, DisciplinaHabilitada
from backend.models.disciplina import Disciplina
from backend.models.turma import Turma
from backend.models.user import User  # Necessário para listar instrutores/comandantes
from backend.services.asset_service import AssetService
from werkzeug.utils import secure_filename

recursos_bp = Blueprint('recursos', __name__, url_prefix='/recursos')

@recursos_bp.route('/')
@login_required
def index():
    """
    Dashboard principal. 
    Admins veem as matérias habilitadas (agrupadas por nome).
    Instrutores veem apenas o que foi encaminhado a eles.
    """
    active_school_id = getattr(current_user, 'temp_active_school_id', None)

    if current_user.role in ['super_admin', 'admin_escola']:
        # Busca IDs de disciplinas habilitadas filtradas por escola e edição
        edicao_id = g.active_edicao.id if g.get('active_edicao') else None
        query = Disciplina.query.join(Turma).join(DisciplinaHabilitada).filter(
            Turma.school_id == active_school_id
        )
        if edicao_id:
            query = query.filter(Turma.edicao_id == edicao_id)
        # Agrupa por materia para não repetir
        materias_vistas = set()
        disciplinas = []
        for d in query.all():
            if d.materia not in materias_vistas:
                materias_vistas.add(d.materia)
                disciplinas.append(d)
        
        return render_template('recursos/admin_dashboard.html', disciplinas=disciplinas)
    
    # Se for instrutor, mostra apenas recursos vinculados a ele para parecer
    if current_user.role == 'instrutor':
        recursos_vinculados = Recurso.query.filter_by(instrutor_id=current_user.id).all()
        return render_template('recursos/admin_analise_lista.html', recursos=recursos_vinculados)
    
    meus_recursos = Recurso.query.options(db.joinedload(Recurso.prova)).filter_by(aluno_id=current_user.id).order_by(Recurso.created_at.desc()).all()
    return render_template('recursos/aluno_lista.html', recursos=meus_recursos)

@recursos_bp.route('/configurar-disciplinas', methods=['GET', 'POST'])
@login_required
def configurar_disciplinas():
    """Checklist baseado no NOME da matéria, mesclando todas as turmas."""
    if current_user.role not in ['super_admin', 'admin_escola']:
        flash("Acesso negado.", "danger")
        return redirect(url_for('main.dashboard'))

    active_school_id = getattr(current_user, 'temp_active_school_id', None)
    
    if request.method == 'POST':
        # Recebemos os NOMES das matérias que o admin quer habilitar
        materias_selecionadas = request.form.getlist('materias_nomes[]')
        
        edicao_id = g.active_edicao.id if g.get('active_edicao') else None
        query = Disciplina.query.join(Turma).filter(Turma.school_id == active_school_id)
        if edicao_id:
            query = query.filter(Turma.edicao_id == edicao_id)
        disciplinas_escola = query.all()
        
        try:
            for d in disciplinas_escola:
                habilitada = DisciplinaHabilitada.query.filter_by(disciplina_id=d.id).first()
                
                # Se o nome da matéria desta disciplina específica está na lista de nomes selecionados
                if d.materia in materias_selecionadas:
                    if not habilitada:
                        db.session.add(DisciplinaHabilitada(disciplina_id=d.id))
                else:
                    if habilitada:
                        db.session.delete(habilitada)
            
            db.session.commit()
            flash("Matérias atualizadas com sucesso!", "success")
            return redirect(url_for('recursos.index'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar: {str(e)}", "danger")

    # GET: Lista NOMES únicos das matérias da escola
    edicao_id = g.active_edicao.id if g.get('active_edicao') else None
    query = db.session.query(Disciplina.materia).join(Turma).filter(
        Turma.school_id == active_school_id
    )
    if edicao_id:
        query = query.filter(Turma.edicao_id == edicao_id)
    materias_unicas = query.distinct().all()
    
    # Pega os nomes das matérias que já têm pelo menos um ID habilitado
    nomes_habilitados = db.session.query(Disciplina.materia).join(DisciplinaHabilitada).distinct().all()
    lista_habilitados = [m[0] for m in nomes_habilitados]

    return render_template('recursos/configurar_disciplinas.html', 
                           materias=[m[0] for m in materias_unicas], 
                           habilitadas=lista_habilitados)

@recursos_bp.route('/admin/provas/<int:disciplina_id>', methods=['GET', 'POST'])
@login_required
def gerenciar_provas(disciplina_id):
    disciplina = Disciplina.query.get_or_404(disciplina_id)
    
    if request.method == 'POST':
        nome_prova = request.form.get('nome_prova')
        if nome_prova:
            # Como todas as turmas usam a mesma prova, vinculamos a este disciplina_id (referência da matéria)
            nova_prova = ProvaRecurso(nome=nome_prova, disciplina_id=disciplina_id)
            db.session.add(nova_prova)
            db.session.commit()
            flash(f"Prova '{nome_prova}' criada!", "success")

    provas = ProvaRecurso.query.filter_by(disciplina_id=disciplina_id).all()
    return render_template('recursos/admin_provas.html', disciplina=disciplina, provas=provas)

@recursos_bp.route('/admin/analisar')
@login_required
def listar_recursos_pendentes():
    """Administrador vê tudo e gerencia encaminhamentos. Instrutor vê o que lhe cabe."""
    active_school_id = getattr(current_user, 'temp_active_school_id', None)
    
    query = Recurso.query.join(ProvaRecurso).join(Disciplina).join(Turma).options(
        db.joinedload(Recurso.prova),
        db.joinedload(Recurso.aluno),
        db.joinedload(Recurso.instrutor)
    ).filter(
        Turma.school_id == active_school_id,
        Turma.edicao_id == session.get('active_edicao_id')
    )

    # Se for instrutor, filtra apenas o que foi destinado a ele
    if current_user.role == 'instrutor':
        recursos = query.filter(Recurso.instrutor_id == current_user.id).all()
    else:
        recursos = query.all()

    import json
    from backend.models.user_school import UserSchool

    # Filtra Comandantes apenas da escola atual
    comandantes = User.query.join(UserSchool).filter(
        UserSchool.school_id == active_school_id,
        User.role.in_(['admin_escola', 'super_admin'])
    ).all()
    
    # Mapeia Instrutores vinculados à disciplina do recurso
    recurso_instrutores_map = {}
    for r in recursos:
        validos = set()
        if r.prova and r.prova.disciplina:
            for assoc in r.prova.disciplina.associacoes_turmas:
                if assoc.instrutor_1 and assoc.instrutor_1.user:
                    u = assoc.instrutor_1.user
                    validos.add((u.id, u.nome_completo, u.posto_graduacao))
                if assoc.instrutor_2 and assoc.instrutor_2.user:
                    u = assoc.instrutor_2.user
                    validos.add((u.id, u.nome_completo, u.posto_graduacao))
        
        recurso_instrutores_map[r.id] = [
            {'id': v[0], 'nome': f"{v[2] or ''} {v[1]}".strip()} for v in validos
        ]

    return render_template('recursos/admin_analise_lista.html', 
                           recursos=recursos, 
                           comandantes=comandantes,
                           instrutores_map=json.dumps(recurso_instrutores_map))

@recursos_bp.route('/admin/encaminhar/<int:recurso_id>', methods=['POST'])
@login_required
def encaminhar_recurso(recurso_id):
    """Administrador encaminha o processo para o próximo nível."""
    if current_user.role not in ['super_admin', 'admin_escola']:
        flash("Acesso negado.", "danger")
        return redirect(url_for('main.dashboard'))

    recurso = Recurso.query.get_or_404(recurso_id)
    destino_id = request.form.get('usuario_destino_id')
    tipo_tramite = request.form.get('tipo_tramite') # 'instrutor' ou 'comandante'
    
    try:
        recurso.instrutor_id = destino_id # Armazena com quem está o processo
        if tipo_tramite == 'instrutor':
            recurso.status = "Com Instrutor"
        else:
            recurso.status = "Com Comandante"
            
        db.session.commit()
        flash("Recurso encaminhado com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao encaminhar: {str(e)}", "danger")
        
    return redirect(url_for('recursos.listar_recursos_pendentes'))

@recursos_bp.route('/admin/detalhes/<int:recurso_id>')
@login_required
def detalhes_recurso(recurso_id):
    """Página dedicada para visualização e redação técnica do parecer/decisão."""
    if current_user.role not in ['super_admin', 'admin_escola', 'instrutor']:
        flash("Acesso negado.", "danger")
        return redirect(url_for('main.dashboard'))
        
    recurso = Recurso.query.get_or_404(recurso_id)
    return render_template('recursos/admin_detalhes_analise.html', r=recurso)

@recursos_bp.route('/admin/salvar_parecer/<int:recurso_id>', methods=['POST'])
@login_required
def salvar_parecer(recurso_id):
    """Lógica para salvar Parecer do Instrutor ou Decisão do Comandante."""
    recurso = Recurso.query.get_or_404(recurso_id)
    tipo_acao = request.form.get('tipo_acao') # 'parecer_instrutor' ou 'decisao_cmt'
    
    try:
        if tipo_acao == 'parecer_instrutor':
            recurso.parecer_instrutor = request.form.get('conteudo_texto')
            recurso.status = "Retornado ao Admin (Parecer)"
            recurso.instrutor_id = None # Libera do painel do instrutor
        else:
            recurso.decisao_comandante = request.form.get('conteudo_texto')
            recurso.status = request.form.get('status_final')
            # A resposta final que o aluno vê na lista dele
            recurso.resposta_admin = recurso.decisao_comandante
            recurso.instrutor_id = None
        
        db.session.commit()
        flash("Documento processado e retornado ao controle administrativo!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao processar documento: {str(e)}", "danger")
        
    return redirect(url_for('recursos.index'))

@recursos_bp.route('/enviar', methods=['GET', 'POST'])
@login_required
def novo_recurso():
    """Aluno vê a matéria unificada."""
    if request.method == 'POST':
        prova_id = request.form.get('prova_id')
        questoes = request.form.getlist('questao_texto[]')
        argumentacoes = request.form.getlist('argumentacao_texto[]')
        arquivos = request.files.getlist('arquivo_anexo[]')

        try:
            for i in range(len(questoes)):
                novo = Recurso(
                    prova_id=prova_id,
                    aluno_id=current_user.id,
                    questao_texto=questoes[i],
                    argumentacao_texto=argumentacoes[i] if i < len(argumentacoes) else ""
                )
                if i < len(arquivos) and arquivos[i].filename != '':
                    filename = AssetService.save_file(arquivos[i], folder='recursos_anexos')
                    novo.arquivo_anexo = filename
                db.session.add(novo)
            db.session.commit()
            flash("Recurso enviado!", "success")
            return redirect(url_for('recursos.index'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro: {str(e)}", "danger")

    active_school_id = current_user._get_active_school_id()
    
    if current_user.role == 'aluno':
        aluno_prof = current_user.aluno_profile
        if aluno_prof and getattr(aluno_prof, 'turma', None):
            if not active_school_id:
                active_school_id = aluno_prof.turma.school_id

    # Forma mais segura e tolerante a falhas estruturais nos dados de teste:
    # 1. Busca todas as provas ativas
    query = ProvaRecurso.query.filter_by(is_active=True).join(Disciplina).join(Turma)
    
    # 2. Filtra pela escola
    if active_school_id:
        query = query.filter(Turma.school_id == active_school_id)
        
    provas_ativas = query.all()
    
    # 3. Agrupa por nome da matéria e verifica se está habilitada
    disciplinas_unicas = {}
    for p in provas_ativas:
        d = p.disciplina
        if d.habilitacao_recurso: # Verifica se a admin marcou como habilitada
            if d.materia not in disciplinas_unicas:
                disciplinas_unicas[d.materia] = d
                
    disciplinas_com_prova = list(disciplinas_unicas.values())
    
    return render_template('recursos/aluno_form.html', disciplinas=disciplinas_com_prova)

@recursos_bp.route('/api/get_provas/<int:disciplina_id>')
@login_required
def api_get_provas(disciplina_id):
    # Lógica importante: busca provas pelo nome da matéria da disciplina selecionada
    d_aluno = Disciplina.query.get_or_404(disciplina_id)
    active_school_id = current_user._get_active_school_id()
    
    if current_user.role == 'aluno':
        aluno_prof = current_user.aluno_profile
        if aluno_prof and getattr(aluno_prof, 'turma', None):
            if not active_school_id:
                active_school_id = aluno_prof.turma.school_id
    
    query = ProvaRecurso.query.join(Disciplina).join(Turma).filter(
        Disciplina.materia == d_aluno.materia,
        ProvaRecurso.is_active == True
    )
    
    if active_school_id:
        query = query.filter(Turma.school_id == active_school_id)
        
    provas = query.all()
    
    return jsonify([{'id': p.id, 'nome': p.nome} for p in provas])