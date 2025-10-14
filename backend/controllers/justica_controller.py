# backend/controllers/justica_controller.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, Response
from flask_login import login_required, current_user
from sqlalchemy import select, or_

# WeasyPrint não é mais necessário aqui, mas pode ser mantido se for usado em outro lugar.
from weasyprint import HTML 

from ..models.database import db
from ..models.aluno import Aluno
from ..models.user import User
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

    alunos_list = []
    if current_user.role != 'aluno':
        alunos = db.session.scalars(select(Aluno).join(User).order_by(User.nome_completo)).all()
        alunos_list = [{'id': a.id, 'nome': a.user.nome_completo, 'matricula': a.user.matricula} for a in alunos]

    return render_template(
        'justica/index.html',
        em_andamento=processos_em_andamento,
        finalizados=processos_finalizados,
        alunos_list=alunos_list
    )

@justica_bp.route('/exportar', methods=['GET'])
@login_required
@admin_or_programmer_required
def exportar_selecao():
    """Renderiza a página de seleção de processos para exportação."""
    processos_finalizados = JusticaService.get_finalized_processos()
    return render_template('justica/exportar_selecao.html', processos=processos_finalizados)

@justica_bp.route('/exportar', methods=['POST'])
@login_required
@admin_or_programmer_required
def exportar_documento():
    """Gera e baixa o arquivo .doc (HTML formatado) com os processos selecionados."""
    processo_ids = request.form.getlist('processo_ids')
    if not processo_ids:
        flash('Nenhum processo selecionado para exportar.', 'warning')
        return redirect(url_for('justica.exportar_selecao'))

    processos = JusticaService.get_processos_por_ids([int(pid) for pid in processo_ids])
    
    # Renderiza o mesmo template HTML que seria usado para o PDF
    rendered_html = render_template('justica/export_bi_template.html', processos=processos)
    
    # Retorna o HTML com o mimetype do Word para que ele abra como um documento editável
    return Response(
        rendered_html,
        mimetype="application/msword",
        headers={"Content-disposition": "attachment; filename=export_processos_BI.doc"}
    )

# ... (restante do arquivo sem alterações)
@justica_bp.route('/novo', methods=['POST'])
@login_required
@admin_or_programmer_required
def novo_processo():
    aluno_id = request.form.get('aluno_id')
    fato = request.form.get('fato')
    observacao = request.form.get('observacao')

    if not aluno_id or not fato:
        flash('Aluno e Fato Constatado são obrigatórios.', 'danger')
        return redirect(url_for('justica.index'))

    success, message = JusticaService.criar_processo(fato, observacao, int(aluno_id), current_user.id)
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

@justica_bp.route('/finalizar/<int:processo_id>', methods=['POST'])
@login_required
@admin_or_programmer_required
def finalizar_processo(processo_id):
    decisao = request.form.get('decisao')
    if not decisao:
        flash('É necessário selecionar uma decisão para finalizar o processo.', 'danger')
        return redirect(url_for('justica.index'))

    success, message = JusticaService.finalizar_processo(processo_id, decisao)
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
    query = (
        select(Aluno)
        .join(User)
        .where(
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