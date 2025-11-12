# Importa 'session' e 'g' (usaremos 'session' para a API)
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, Response, g, session
from flask_login import login_required, current_user
from sqlalchemy import select, or_
import locale

from ..models.database import db
from ..models.aluno import Aluno
from ..models.user import User
from ..models.turma import Turma
from ..models.discipline_rule import DisciplineRule
from ..models.school import School # Necessário para buscar a escola
from ..models.user_school import UserSchool # Necessário para a consulta
from ..services.justica_service import JusticaService
from utils.decorators import admin_or_programmer_required

justica_bp = Blueprint('justica', __name__, url_prefix='/justica-e-disciplina')

@justica_bp.route('/')
@login_required
def index():
    """Página principal de Justiça e Disciplina."""
    processos = JusticaService.get_processos_para_usuario(current_user)
    
    processos_em_andamento = [p for p in processos if p.status != 'Finalizado']
    processos_finalizados = [p for p in processos if p.status == 'Finalizado']

    # ### INÍCIO DA ALTERAÇÃO ###
    # Verifica o tipo de NPCCAL da escola ativa para decidir se a pontuação se aplica.
    active_school = g.get('active_school') 
    fatos_predefinidos = []
    permite_pontuacao = False  # Por padrão, não permite pontuação

    if active_school:
        npccal_type_da_escola = active_school.npccal_type
        
        # A pontuação SÓ se aplica a 'cspm' e 'cbfpm', conforme os PDFs.
        if npccal_type_da_escola in ['cspm', 'cbfpm']:
            permite_pontuacao = True
            
            # Carrega as regras de disciplina corretas do banco
            fatos_predefinidos = db.session.scalars(
                select(DisciplineRule)
                .where(DisciplineRule.npccal_type == npccal_type_da_escola)
                .order_by(DisciplineRule.id)
            ).all()
        
        # Se for 'ctsp', permite_pontuacao continuará False
        # e fatos_predefinidos (regras) será uma lista vazia.
    # ### FIM DA ALTERAÇÃO ###

    return render_template(
        'justica/index.html',
        em_andamento=processos_em_andamento,
        finalizados=processos_finalizados,
        fatos_predefinidos=fatos_predefinidos,
        permite_pontuacao=permite_pontuacao  # <-- Passa a flag para o template
    )

@justica_bp.route('/analise')
@login_required
@admin_or_programmer_required
def analise():
    
    # ### INÍCIO DA ALTERAÇÃO ###
    # Proteção: Garante que escolas 'ctsp' não acessem a análise
    active_school = g.get('active_school')
    if not active_school or active_school.npccal_type not in ['cspm', 'cbfpm']:
        flash('A Análise de Dados não se aplica a esta escola.', 'info')
        return redirect(url_for('justica.index'))
    # ### FIM DA ALTERAÇÃO ###

    # --- INÍCIO DA CORREÇÃO ---
    # O log de erro (UndefinedError: 'dict object' has no attribute 'status_counts')
    # indica que o template 'analise.html' espera receber uma variável 'dados'
    # que contenha um dicionário aninhado chamado 'status_counts'.
    
    # Provavelmente, a função do serviço retorna o dicionário de contagem DIRETAMENTE.
    contagem_de_status = JusticaService.get_analise_disciplinar_data()
    
    # Portanto, precisamos "embrulhar" essa contagem na estrutura que o template espera.
    dados_para_template = {
        'status_counts': contagem_de_status
        # Se a função de serviço retornar outros dados, adicione-os aqui também.
        # Ex: 'outros_dados': JusticaService.get_outros_dados()
    }
    
    # Passamos o dicionário 'dados_para_template' (que agora contém 'status_counts')
    # para o template como a variável 'dados'.
    return render_template('justica/analise.html', dados=dados_para_template)
    # --- FIM DA CORREÇÃO ---


@justica_bp.route('/finalizar/<int:processo_id>', methods=['POST'])
@login_required
@admin_or_programmer_required
def finalizar_processo(processo_id):
    decisao = request.form.get('decisao_final')
    fundamentacao = request.form.get('fundamentacao')
    detalhes_sancao = request.form.get('detalhes_sancao')

    if not decisao or not fundamentacao:
        flash('É necessário selecionar uma decisão e preencher a fundamentação.', 'danger')
        return redirect(url_for('justica.index'))
    
    if decisao in ['Advertência', 'Repreensão'] and not detalhes_sancao:
        flash('Para Advertência ou Repreensão, o campo de detalhes da sanção é obrigatório.', 'danger')
        return redirect(url_for('justica.index'))

    success, message = JusticaService.finalizar_processo(processo_id, decisao, fundamentacao, detalhes_sancao)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('justica.index'))
    
@justica_bp.route('/novo', methods=['POST'])
@login_required
@admin_or_programmer_required
def novo_processo():
    
    # ### INÍCIO DA ALTERAÇÃO ###
    # Proteção: Garante que escolas 'ctsp' não criem novos processos
    active_school = g.get('active_school')
    if not active_school or active_school.npccal_type not in ['cspm', 'cbfpm']:
        flash('Não é possível registrar infrações com pontuação para esta escola.', 'danger')
        return redirect(url_for('justica.index'))
    # ### FIM DA ALTERAÇÃO ###
    
    aluno_id = request.form.get('aluno_id')
    fato_descricao = request.form.get('fato_descricao') 
    fato_pontos = request.form.get('fato_pontos')
    observacao = request.form.get('observacao')

    if not aluno_id or not fato_descricao:
        flash('Aluno e Fato Constatado são obrigatórios.', 'danger')
        return redirect(url_for('justica.index'))

    try:
        pontos = float(fato_pontos) if fato_pontos else 0.0
    except ValueError:
        pontos = 0.0

    success, message = JusticaService.criar_processo(
        fato_descricao, 
        observacao, 
        int(aluno_id), 
        current_user.id,
        pontos
    )
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/dar-ciente/<int:processo_id>', methods=['POST'])
@login_required
def dar_ciente(processo_id):
    success, message = JusticaService.registrar_ciente(processo_id, current_user)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/enviar-defesa/<int:processo_id>', methods=['POST'])
@login_required
def enviar_defesa(processo_id):
    defesa = request.form.get('defesa')
    if not defesa:
        flash('O texto da defesa não pode estar vazio.', 'danger')
        return redirect(url_for('justica.index'))
    
    success, message = JusticaService.enviar_defesa(processo_id, defesa, current_user)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/deletar/<int:processo_id>', methods=['POST'])
@login_required
@admin_or_programmer_required
def deletar_processo(processo_id):
    success, message = JusticaService.deletar_processo(processo_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/api/alunos')
@login_required
@admin_or_programmer_required
def api_get_alunos():
    search = request.args.get('q', '').lower()
    
    # --- INÍCIO DA CORREÇÃO DEFINITIVA ---
    # A variável 'g' não é populada em rotas de API que não usam 'render_template'.
    # Temos de buscar a escola ativa manually a partir da 'session',
    # replicando a lógica que existe em 'app.py'.

    school_id_to_load = None
    if current_user.role in ['super_admin', 'programador']:
        school_id_to_load = session.get('view_as_school_id')
    elif hasattr(current_user, 'user_schools') and current_user.user_schools:
        school_id_to_load = current_user.user_schools[0].school_id

    if not school_id_to_load:
        return jsonify({'error': 'Nenhuma escola ativa selecionada na sessão.'}), 400
    
    # Esta é a consulta correta. Ela filtra os Alunos com base
    # no vínculo do User (UserSchool) com a escola ativa.
    query = (
        select(Aluno)
        .join(User, Aluno.user_id == User.id)
        .join(UserSchool, User.id == UserSchool.user_id)
        .where(
            UserSchool.school_id == school_id_to_load, # 1. Filtra pela escola correta
            User.role == 'aluno',                      # 2. Garante que é um aluno
            or_(                                       # 3. Filtra pela busca
                User.nome_completo.ilike(f'%{search}%'),
                User.matricula.ilike(f'%{search}%')
            )
        )
        .order_by(User.nome_completo)
        .limit(20)
    )
    # --- FIM DA CORREÇÃO DEFINITIVA ---
    
    alunos = db.session.scalars(query).all()
    results = [{'id': a.id, 'text': f"{a.user.nome_completo} ({a.user.matricula})"} for a in alunos]
    return jsonify(results)

@justica_bp.route('/api/aluno-details/<int:aluno_id>')
@login_required
@admin_or_programmer_required
def api_get_aluno_details(aluno_id):
    aluno = db.session.get(Aluno, aluno_id)
    if not aluno or not aluno.user:
        return jsonify({'error': 'Aluno não encontrado'}), 404
    
    details = {
        'posto_graduacao': aluno.user.posto_graduacao or 'POSTO/GRADUAÇÃO',
        'matricula': aluno.user.matricula or 'MATRÍCULA',
        'nome_completo': aluno.user.nome_completo or 'NOME DO ALUNO'
    }
    return jsonify(details)

@justica_bp.route('/exportar', methods=['GET', 'POST'])
@login_required
@admin_or_programmer_required
def exportar_selecao():
    
    # ### INÍCIO DA ALTERAÇÃO ###
    # Proteção: Garante que escolas 'ctsp' não acessem a exportação
    active_school = g.get('active_school')
    if not active_school or active_school.npccal_type not in ['cspm', 'cbfpm']:
        flash('A exportação não se aplica a esta escola.', 'info')
        return redirect(url_for('justica.index'))
    # ### FIM DA ALTERAÇÃO ###
    
    try:
        locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil')
        except locale.Error:
            pass 

    if request.method == 'POST':
        processo_ids = request.form.getlist('processo_ids')
        if not processo_ids:
            flash('Nenhum processo selecionado para exportar.', 'warning')
            return redirect(url_for('justica.exportar_selecao'))

        processos = JusticaService.get_processos_por_ids([int(pid) for pid in processo_ids])
        
        rendered_html = render_template('justica/export_bi_template.html', processos=processos)
        
        return Response(
            rendered_html,
            mimetype="application/msword",
            headers={"Content-disposition": "attachment; filename=export_processos_BI.doc"}
        )
    
    processos_finalizados = JusticaService.get_finalized_processos()
    return render_template('justica/exportar_selecao.html', processos=processos_finalizados)