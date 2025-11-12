# Importa 'session' e 'g' (usaremos 'session' para a API)
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, Response, g, session
from flask_login import login_required, current_user
from sqlalchemy import select, or_
import locale

# ### INÍCIO DA ALTERAÇÃO (FADA) ###
from weasyprint import HTML
from io import BytesIO
# ### FIM DA ALTERAÇÃO ###

from ..models.database import db
from ..models.aluno import Aluno
from ..models.user import User
from ..models.turma import Turma
from ..models.discipline_rule import DisciplineRule
from ..models.school import School # Necessário para buscar a escola
from ..models.user_school import UserSchool # Necessário para a consulta
# ### INÍCIO DA ALTERAÇÃO (FADA) ###
from ..models.fada_avaliacao import FadaAvaliacao # Importa o novo modelo
# ### FIM DA ALTERAÇÃO ###
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

    active_school = g.get('active_school') 
    fatos_predefinidos = []
    permite_pontuacao = False  # Por padrão, não permite pontuação (para CTSP)

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
    
    return render_template(
        'justica/index.html',
        em_andamento=processos_em_andamento,
        finalizados=processos_finalizados,
        fatos_predefinidos=fatos_predefinidos,
        permite_pontuacao=permite_pontuacao
    )

@justica_bp.route('/analise')
@login_required
@admin_or_programmer_required
def analise():
    
    active_school = g.get('active_school')
    if not active_school or not active_school.npccal_type in ['cspm', 'cbfpm']:
        flash('A Análise de Dados não se aplica a esta escola.', 'info')
        return redirect(url_for('justica.index'))

    # ... (seu código de análise existente) ...
    contagem_de_status = JusticaService.get_analise_disciplinar_data()
    dados_para_template = { 'status_counts': contagem_de_status }
    return render_template('justica/analise.html', dados=dados_para_template)


@justica_bp.route('/finalizar/<int:processo_id>', methods=['POST'])
@login_required
@admin_or_programmer_required
def finalizar_processo(processo_id):
    # ... (seu código de finalizar_processo existente) ...
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
    
    aluno_id = request.form.get('aluno_id')
    fato_descricao = request.form.get('fato_descricao') 
    fato_pontos = request.form.get('fato_pontos')
    observacao = request.form.get('observacao')

    if not aluno_id or not fato_descricao:
        flash('Aluno e Fato Constatado são obrigatórios.', 'danger')
        return redirect(url_for('justica.index'))

    # ### INÍCIO DA ALTERAÇÃO (LÓGICA CTSP) ###
    # Se a escola for CTSP, força os pontos a 0.0,
    # caso contrário, usa o valor do formulário (que pode ser 0.0 ou mais).
    active_school = g.get('active_school')
    if active_school and active_school.npccal_type == 'ctsp':
        pontos = 0.0
    else:
        try:
            pontos = float(fato_pontos) if fato_pontos else 0.0
        except ValueError:
            pontos = 0.0
    # ### FIM DA ALTERAÇÃO ###

    success, message = JusticaService.criar_processo(
        fato_descricao, 
        observacao, 
        int(aluno_id), 
        current_user.id,
        pontos
    )
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('justica.index'))

# ... (dar_ciente, enviar_defesa, deletar_processo, api_get_alunos, api_get_aluno_details...) ...
# ... (MANTENHA TODAS AS SUAS ROTAS EXISTENTES AQUI) ...

@justica_bp.route('/exportar', methods=['GET', 'POST'])
@login_required
@admin_or_programmer_required
def exportar_selecao():
    
    active_school = g.get('active_school')
    if not active_school or not active_school.npccal_type in ['cspm', 'cbfpm']:
        flash('A exportação não se aplica a esta escola.', 'info')
        return redirect(url_for('justica.index'))
    
    # ... (seu código de exportar_selecao existente) ...
    try:
        locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
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

# ### INÍCIO DAS NOVAS ROTAS FADA ###

@justica_bp.route('/fada')
@login_required
@admin_or_programmer_required
def fada_lista_alunos():
    """Mostra a lista de alunos da escola para avaliação FADA."""
    active_school = g.get('active_school')
    if not active_school:
        flash('Nenhuma escola ativa selecionada.', 'danger')
        return redirect(url_for('main.dashboard'))
        
    alunos = JusticaService.get_alunos_para_fada(active_school.id)
    return render_template('justica/fada_lista_alunos.html', alunos=alunos)

@justica_bp.route('/fada/avaliar/<int:aluno_id>', methods=['GET', 'POST'])
@login_required
@admin_or_programmer_required
def fada_avaliar_aluno(aluno_id):
    """Exibe o formulário FADA para um aluno específico."""
    aluno = db.session.get(Aluno, aluno_id)
    if not aluno or not aluno.user:
        flash('Aluno não encontrado.', 'danger')
        return redirect(url_for('justica.fada_lista_alunos'))

    if request.method == 'POST':
        success, message, avaliacao_id = JusticaService.salvar_fada(
            request.form, 
            aluno_id, 
            current_user.id
        )
        
        if success:
            flash(message, 'success')
            # Redireciona para o PDF recém-criado
            return redirect(url_for('justica.fada_gerar_pdf', avaliacao_id=avaliacao_id))
        else:
            flash(message, 'danger')
            
    return render_template('justica/fada_formulario.html', aluno=aluno)

@justica_bp.route('/fada/pdf/<int:avaliacao_id>')
@login_required
@admin_or_programmer_required
def fada_gerar_pdf(avaliacao_id):
    """Gera o PDF de uma avaliação FADA preenchida."""
    avaliacao = JusticaService.get_fada_por_id(avaliacao_id)
    if not avaliacao:
        flash('Avaliação FADA não encontrada.', 'danger')
        return redirect(url_for('justica.fada_lista_alunos'))

    # Renderiza o template HTML
    html_string = render_template('justica/fada_pdf_template.html', avaliacao=avaliacao)
    
    # Gera o PDF usando WeasyPrint
    pdf_file = HTML(string=html_string).write_pdf()
    
    return Response(
        pdf_file,
        mimetype="application/pdf",
        headers={"Content-disposition": f"attachment; filename=fada_aluno_{avaliacao.aluno_id}.pdf"}
    )

# ### FIM DAS NOVAS ROTAS FADA ###