# backend/controllers/justica_controller.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, Response, g, session
from flask_login import login_required, current_user
from sqlalchemy import select, or_
import locale
from datetime import datetime 

from weasyprint import HTML
from io import BytesIO
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from ..models.database import db
from ..models.aluno import Aluno
from ..models.user import User
from ..models.turma import Turma
from ..models.discipline_rule import DisciplineRule
from ..models.school import School
from ..models.user_school import UserSchool
from ..models.fada_avaliacao import FadaAvaliacao
from ..models.ciclo import Ciclo
from ..services.justica_service import JusticaService
from ..services.aluno_service import AlunoService
# CORREÇÃO: Importa o decorador específico de CAL
from utils.decorators import cal_required, admin_or_programmer_required

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
    permite_pontuacao = False

    if active_school:
        npccal_type_da_escola = active_school.npccal_type

        if npccal_type_da_escola in ['cspm', 'cbfpm']:
            permite_pontuacao = True

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
@cal_required 
def analise():
    active_school = g.get('active_school')
    if not active_school or not active_school.npccal_type in ['cspm', 'cbfpm', 'ctsp']:
        flash('A Análise de Dados não se aplica a esta escola.', 'info')
        return redirect(url_for('justica.index'))

    contagem_de_status = JusticaService.get_analise_disciplinar_data()

    dados_para_template = {
        'status_counts': contagem_de_status['status_counts'],
        'common_facts': contagem_de_status['common_facts'],
        'top_alunos': contagem_de_status['top_alunos']
    }

    return render_template('justica/analise.html', dados=dados_para_template)


@justica_bp.route('/finalizar/<int:processo_id>', methods=['POST'])
@login_required
@cal_required 
def finalizar_processo(processo_id):
    decisao = request.form.get('decisao_final')
    fundamentacao = request.form.get('fundamentacao')
    detalhes_sancao = request.form.get('detalhes_sancao')
    turnos_sustacao = request.form.get('turnos_sustacao')

    if not decisao or not fundamentacao:
        flash('É necessário selecionar uma decisão e preencher a fundamentação.', 'danger')
        return redirect(url_for('justica.index'))

    detalhes_final = detalhes_sancao

    if decisao == 'Sustação da Dispensa' and turnos_sustacao:
        detalhes_final = f"Sustação da Dispensa de {turnos_sustacao}"

    success, message = JusticaService.finalizar_processo(processo_id, decisao, fundamentacao, detalhes_final)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/novo', methods=['POST'])
@login_required
@cal_required 
def novo_processo():
    aluno_id = request.form.get('aluno_id')
    fato_descricao = request.form.get('fato_descricao')
    fato_pontos = request.form.get('fato_pontos')
    observacao = request.form.get('observacao')
    
    # Novos campos para suportar cálculo
    regra_id = request.form.get('regra_id') # Se vier de um select
    data_fato_str = request.form.get('data_fato') # Opcional, senão usa hoje

    if not aluno_id or not fato_descricao:
        flash('Aluno e Fato Constatado são obrigatórios.', 'danger')
        return redirect(url_for('justica.index'))

    active_school = g.get('active_school')
    
    codigo_infracao = None
    pontos = 0.0
    
    # Tenta pegar código da infração se uma regra foi selecionada (melhor para cálculo)
    if regra_id:
        regra = db.session.get(DisciplineRule, regra_id)
        if regra:
            codigo_infracao = regra.codigo
            pontos = regra.pontos
    elif fato_pontos:
        try:
            pontos = float(fato_pontos)
        except ValueError:
            pontos = 0.0
            
    if active_school and active_school.npccal_type == 'ctsp':
        pontos = 0.0

    data_ocorrencia = None
    if data_fato_str:
        try:
            data_ocorrencia = datetime.strptime(data_fato_str, '%Y-%m-%d').date()
        except:
            pass

    success, message = JusticaService.criar_processo(
        fato_descricao,
        observacao,
        int(aluno_id),
        current_user.id,
        pontos,
        codigo_infracao=codigo_infracao,
        data_ocorrencia=data_ocorrencia
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
@cal_required 
def deletar_processo(processo_id):
    success, message = JusticaService.deletar_processo(processo_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/api/alunos')
@login_required
@cal_required 
def api_get_alunos():
    search = request.args.get('q', '').lower()

    school_id_to_load = None
    if current_user.role in ['super_admin', 'programador']:
        school_id_to_load = session.get('view_as_school_id')
    # Tenta pegar do contexto ativo (fix para CAL)
    elif hasattr(current_user, 'temp_active_school_id'):
        school_id_to_load = current_user.temp_active_school_id
    elif hasattr(current_user, 'user_schools') and current_user.user_schools:
        school_id_to_load = current_user.user_schools[0].school_id

    if not school_id_to_load:
        return jsonify({'error': 'Nenhuma escola ativa selecionada na sessão.'}), 400

    query = (
        select(Aluno)
        .join(User, Aluno.user_id == User.id)
        .join(UserSchool, User.id == UserSchool.user_id)
        .where(
            UserSchool.school_id == school_id_to_load,
            User.role == 'aluno',
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
@cal_required 
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
@cal_required 
def exportar_selecao():

    active_school = g.get('active_school')
    if not active_school or not active_school.npccal_type in ['cspm', 'cbfpm', 'ctsp']:
        flash('A exportação não se aplica a esta escola.', 'info')
        return redirect(url_for('justica.index'))

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

# ### ROTAS FADA ###

@justica_bp.route('/fada')
@login_required
@cal_required 
def fada_lista_alunos():
    """Mostra a lista de alunos da escola para avaliação FADA."""
    active_school = g.get('active_school')
    if not active_school:
        flash('Nenhuma escola ativa selecionada.', 'danger')
        return redirect(url_for('main.dashboard'))

    if active_school.npccal_type == 'ctsp':
        flash('A avaliação FADA não se aplica a esta escola.', 'info')
        return redirect(url_for('justica.index'))

    alunos = JusticaService.get_alunos_para_fada(active_school.id)
    return render_template('justica/fada_lista_alunos.html', alunos=alunos)

@justica_bp.route('/fada/avaliar/<int:aluno_id>', methods=['GET', 'POST'])
@login_required
@cal_required 
def fada_avaliar_aluno(aluno_id):
    """Exibe o formulário FADA com cálculo automático (GET) ou salva (POST)."""

    active_school = g.get('active_school')
    if active_school and active_school.npccal_type == 'ctsp':
        flash('A avaliação FADA não se aplica a esta escola.', 'info')
        return redirect(url_for('justica.index'))

    aluno = db.session.get(Aluno, aluno_id)
    if not aluno or not aluno.user:
        flash('Aluno não encontrado.', 'danger')
        return redirect(url_for('justica.fada_lista_alunos'))

    # Carrega ciclos para o select
    ciclos = db.session.query(Ciclo).filter_by(school_id=active_school.id).all()
    ciclo_id = request.args.get('ciclo_id', type=int) or (ciclos[-1].id if ciclos else None)

    default_name = current_user.nome_completo or current_user.username
    if active_school and current_user.role == 'admin_escola':
        default_name = f"Administrador {active_school.nome}"

    # CÁLCULO AUTOMÁTICO DA PRÉVIA
    dados_previa = None
    if ciclo_id:
        dados_previa = JusticaService.calcular_previa_fada(aluno_id, ciclo_id)

    if request.method == 'POST':
        nome_avaliador_custom = request.form.get('nome_avaliador_custom', default_name)
        
        # Recalcula para garantir que os dados salvos estejam frescos, ou confia no form
        # Aqui optamos por passar o form, mas o service pode validar
        success, message, avaliacao_id = JusticaService.salvar_fada(
            request.form,
            aluno_id,
            current_user.id,
            nome_avaliador_custom,
            dados_calculados=None # Se quiser forçar o cálculo no save, passe dados_previa aqui
        )

        if success:
            flash(message, 'success')
            return redirect(url_for('justica.fada_gerar_pdf', avaliacao_id=avaliacao_id))
        else:
            flash(message, 'danger')
            default_name = nome_avaliador_custom

    return render_template(
        'justica/fada_formulario.html',
        aluno=aluno,
        default_name=default_name,
        ciclos=ciclos,
        ciclo_atual=ciclo_id,
        dados_previa=dados_previa # Passa a prévia calculada para o template preencher os campos
    )

@justica_bp.route('/fada/pdf/<int:avaliacao_id>')
@login_required
@cal_required 
def fada_gerar_pdf(avaliacao_id):
    """Gera o PDF de uma avaliação FADA preenchida."""

    active_school = g.get('active_school')
    if active_school and active_school.npccal_type == 'ctsp':
        flash('A avaliação FADA não se aplica a esta escola.', 'info')
        return redirect(url_for('justica.index'))

    avaliacao = JusticaService.get_fada_por_id(avaliacao_id)
    if not avaliacao:
        flash('Avaliação FADA não encontrada.', 'danger')
        return redirect(url_for('justica.fada_lista_alunos'))

    avaliador_nome = avaliacao.nome_avaliador_custom

    if not avaliador_nome:
        avaliador = avaliacao.avaliador
        escola = g.get('active_school')

        avaliador_nome = "Avaliador"
        if avaliador:
            avaliador_nome = avaliador.nome_completo or avaliador.username

        if escola and avaliador and avaliador.role == 'admin_escola':
             avaliador_nome = f"Administrador {escola.nome}"

    try:
        data_geracao = datetime.now(ZoneInfo("America/Sao_Paulo"))
    except Exception:
        data_geracao = datetime.now()

    html_string = render_template(
        'justica/fada_pdf_template.html',
        avaliacao=avaliacao,
        aluno=avaliacao.aluno,
        avaliador_nome=avaliador_nome,
        data_geracao=data_geracao
    )

    pdf_file = HTML(string=html_string).write_pdf()

    return Response(
        pdf_file,
        mimetype="application/pdf",
        headers={"Content-disposition": f"attachment; filename=fada_aluno_{avaliacao.aluno_id}.pdf"}
    )

# --- NOVA ROTA: MALA DIRETA (PUNIÇÃO COLETIVA) ---
@justica_bp.route('/registrar-em-massa', methods=['GET', 'POST'])
@login_required
@cal_required 
def registrar_em_massa():
    active_school = g.get('active_school')
    
    if request.method == 'POST':
        try:
            alunos_ids = request.form.getlist('alunos_selecionados')
            regra_id = request.form.get('regra_id')
            data_fato_str = request.form.get('data_fato')
            descricao_base = request.form.get('descricao')
            
            if not alunos_ids or not regra_id:
                flash('Selecione pelo menos um aluno e uma infração.', 'warning')
                return redirect(url_for('justica.registrar_em_massa'))

            regra = db.session.get(DisciplineRule, regra_id)
            data_fato = None
            if data_fato_str:
                data_fato = datetime.strptime(data_fato_str, '%Y-%m-%d').date()

            count = 0
            for aluno_id in alunos_ids:
                # Usa o service existente para garantir consistência
                JusticaService.criar_processo(
                    descricao_base,
                    "", # Observação vazia
                    int(aluno_id),
                    current_user.id,
                    regra.pontos,
                    codigo_infracao=regra.codigo,
                    data_ocorrencia=data_fato
                )
                count += 1
            
            flash(f'Sucesso! {count} processos foram abertos.', 'success')
            return redirect(url_for('justica.index'))

        except Exception as e:
            flash(f'Erro ao registrar em massa: {str(e)}', 'danger')

    turmas = Turma.query.filter_by(school_id=active_school.id).all()
    tipo_npccal = active_school.npccal_type or 'cbfpm'
    regras = DisciplineRule.query.filter_by(npccal_type=tipo_npccal).order_by(DisciplineRule.codigo).all()

    return render_template('justica/registrar_em_massa.html', turmas=turmas, regras=regras)

@justica_bp.route('/api/alunos-por-turma/<int:turma_id>')
@login_required
def api_alunos_por_turma(turma_id):
    alunos = Aluno.query.filter_by(turma_id=turma_id).join(Aluno.user).order_by(Aluno.num_aluno).all()
    data = [{'id': a.id, 'nome': a.user.nome_completo, 'numero': a.num_aluno, 'matricula': a.user.matricula} for a in alunos]
    return jsonify(data)