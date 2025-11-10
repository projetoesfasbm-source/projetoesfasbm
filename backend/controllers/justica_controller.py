# backend/controllers/justica_controller.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, Response, g
from flask_login import login_required, current_user
from sqlalchemy import select, or_
import locale

from ..models.database import db
from ..models.aluno import Aluno
from ..models.user import User
from ..models.turma import Turma
from ..models.discipline_rule import DisciplineRule # <-- Importa o novo modelo
from ..services.justica_service import JusticaService
from utils.decorators import admin_or_programmer_required

justica_bp = Blueprint('justica', __name__, url_prefix='/justica-e-disciplina')

# --- A antiga lista FATOS_PREDEFINIDOS foi removida daqui ---

@justica_bp.route('/')
@login_required
def index():
    """Página principal de Justiça e Disciplina."""
    processos = JusticaService.get_processos_para_usuario(current_user)
    
    processos_em_andamento = [p for p in processos if p.status != 'Finalizado']
    processos_finalizados = [p for p in processos if p.status == 'Finalizado']

    # --- NOVA LÓGICA: Busca fatos do banco de dados ---
    # 1. Identifica qual escola está ativa para o usuário
    active_school = g.get('active_school') 
    npccal_type_da_escola = 'ctsp' # Valor padrão de segurança
    
    if active_school:
        npccal_type_da_escola = active_school.npccal_type
    
    # 2. Busca apenas as regras que se aplicam a essa escola
    # Ex: Se a escola é CBFPM, só trará as 110 regras de soldado.
    regras_db = db.session.scalars(
        select(DisciplineRule)
        .where(DisciplineRule.npccal_type == npccal_type_da_escola)
        .order_by(DisciplineRule.id)
    ).all()
    # --------------------------------------------------

    return render_template(
        'justica/index.html',
        em_andamento=processos_em_andamento,
        finalizados=processos_finalizados,
        fatos_predefinidos=regras_db # Passa a lista vinda do Banco para o template
    )

@justica_bp.route('/analise')
@login_required
@admin_or_programmer_required
def analise():
    """Página de análise de dados e gráficos."""
    dados_analise = JusticaService.get_analise_disciplinar_data()
    return render_template('justica/analise.html', dados=dados_analise)

@justica_bp.route('/novo', methods=['POST'])
@login_required
@admin_or_programmer_required
def novo_processo():
    aluno_id = request.form.get('aluno_id')
    # O formulário agora envia a descrição E os pontos em campos separados
    fato_descricao = request.form.get('fato_descricao') 
    fato_pontos = request.form.get('fato_pontos')
    observacao = request.form.get('observacao')

    if not aluno_id or not fato_descricao:
        flash('Aluno e Fato Constatado são obrigatórios.', 'danger')
        return redirect(url_for('justica.index'))

    # Converte os pontos para número (padrão 0.0 se falhar)
    try:
        pontos = float(fato_pontos) if fato_pontos else 0.0
    except ValueError:
        pontos = 0.0

    # Chama o serviço passando os novos dados
    success, message = JusticaService.criar_processo(
        fato_descricao, 
        observacao, 
        int(aluno_id), 
        current_user.id,
        pontos # <-- Passa os pontos para serem salvos no processo
    )
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('justica.index'))

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
    
    # Garante que só retorna alunos da mesma escola que o administrador está visualizando
    active_school = g.get('active_school')
    if not active_school:
        return jsonify({'error': 'Nenhuma escola ativa selecionada'}), 400
    
    query = (
        select(Aluno)
        .join(User)
        .join(Turma) # Join com Turma para filtrar por escola
        .where(
            Turma.school_id == active_school.id,
            or_(
                User.nome_completo.ilike(f'%{search}%'),
                User.matricula.ilike(f'%{search}%')
            )
        )
        .order_by(User.nome_completo)
        .limit(20)
    )
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
    # Tenta configurar o locale para datas em português
    try:
        locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil')
        except locale.Error:
             pass # Usa o padrão do sistema se falhar

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