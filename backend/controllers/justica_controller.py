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
from ..models.elogio import Elogio # Importação necessária
from ..services.justica_service import JusticaService
from ..services.aluno_service import AlunoService
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
    turmas = []
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
        
        # Carrega turmas para o seletor de alunos
        turmas = db.session.scalars(
            select(Turma).where(Turma.school_id == active_school.id).order_by(Turma.nome)
        ).all()

    atributos_fada = [
        (1, 'Expressão'), (2, 'Planejamento'), (3, 'Perseverança'), (4, 'Apresentação'),
        (5, 'Lealdade'), (6, 'Tato'), (7, 'Equilíbrio'), (8, 'Disciplina'), (9, 'Responsabilidade'),
        (10, 'Maturidade'), (11, 'Assiduidade'), (12, 'Pontualidade'), (13, 'Dicção'),
        (14, 'Liderança'), (15, 'Relacionamento'), (16, 'Ética'), (17, 'Produtividade'), (18, 'Eficiência')
    ]

    return render_template(
        'justica/index.html',
        em_andamento=processos_em_andamento,
        finalizados=processos_finalizados,
        fatos_predefinidos=fatos_predefinidos,
        turmas=turmas,
        permite_pontuacao=permite_pontuacao,
        atributos_fada=atributos_fada,
        hoje=datetime.today().strftime('%Y-%m-%d')
    )

# --- ROTA UNIFICADA DE REGISTRO (INFRAÇÃO OU ELOGIO) ---
@justica_bp.route('/registrar-em-massa', methods=['POST'])
@login_required
@cal_required 
def registrar_em_massa():
    active_school = g.get('active_school')
    tipo_registro = request.form.get('tipo_registro') # 'infracao' ou 'elogio'
    alunos_ids = request.form.getlist('alunos_selecionados')
    
    # Fallback para formulário antigo (aluno único)
    if not alunos_ids:
        single_id = request.form.get('aluno_id')
        if single_id: alunos_ids = [single_id]
    
    if not alunos_ids:
        flash('Nenhum aluno selecionado.', 'warning')
        return redirect(url_for('justica.index'))

    data_fato_str = request.form.get('data_fato')
    descricao = request.form.get('descricao') or request.form.get('fato_descricao')
    data_fato = datetime.strptime(data_fato_str, '%Y-%m-%d').date() if data_fato_str else datetime.now().date()

    count = 0
    try:
        if tipo_registro == 'infracao':
            regra_id = request.form.get('regra_id')
            # Se não tiver regra_id (modo manual), tenta pegar pontos direto
            pontos = float(request.form.get('fato_pontos') or 0.0)
            codigo = None
            
            if regra_id:
                regra = db.session.get(DisciplineRule, regra_id)
                if regra:
                    pontos = regra.pontos
                    codigo = regra.codigo

            obs = request.form.get('observacao', '')

            for aluno_id in alunos_ids:
                JusticaService.criar_processo(
                    descricao,
                    obs,
                    int(aluno_id),
                    current_user.id,
                    pontos,
                    codigo_infracao=codigo,
                    data_ocorrencia=data_fato
                )
                count += 1
            flash(f'Sucesso! {count} infrações registradas.', 'success')

        elif tipo_registro == 'elogio':
            attr1 = request.form.get('atributo_1')
            attr2 = request.form.get('atributo_2')
            # Só pontua se for escola que permite e tiver atributo selecionado
            pontos = 0.5 if (attr1 or attr2) and active_school.npccal_type in ['cbfpm', 'cspm'] else 0.0

            for aluno_id in alunos_ids:
                novo_elogio = Elogio(
                    aluno_id=int(aluno_id),
                    registrado_por_id=current_user.id,
                    data_elogio=data_fato,
                    descricao=descricao,
                    pontos=pontos,
                    atributo_1=int(attr1) if attr1 else None,
                    atributo_2=int(attr2) if attr2 else None
                )
                db.session.add(novo_elogio)
                count += 1
            db.session.commit()
            flash(f'Sucesso! {count} elogios registrados.', 'success')
        
        # Caso não seja nem infração nem elogio (ex: rota antiga /novo redirecionada)
        else:
             # Assume infração manual
             obs = request.form.get('observacao', '')
             pontos = float(request.form.get('fato_pontos') or 0.0)
             for aluno_id in alunos_ids:
                JusticaService.criar_processo(
                    descricao,
                    obs,
                    int(aluno_id),
                    current_user.id,
                    pontos,
                    data_ocorrencia=data_fato
                )
                count += 1
             flash(f'Sucesso! {count} registros criados.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao registrar: {str(e)}', 'danger')

    return redirect(url_for('justica.index'))

# Rota legado para manter compatibilidade se o template antigo chamar
@justica_bp.route('/novo', methods=['POST'])
@login_required
@cal_required
def novo_processo():
    # Redireciona para a nova rota unificada, passando os dados
    return registrar_em_massa()

# --- ROTAS DE SUPORTE E ANÁLISE ---

@justica_bp.route('/analise')
@login_required
@cal_required 
def analise():
    active_school = g.get('active_school')
    if not active_school or not active_school.npccal_type in ['cspm', 'cbfpm', 'ctsp']:
        flash('A Análise de Dados não se aplica a esta escola.', 'info')
        return redirect(url_for('justica.index'))

    contagem = JusticaService.get_analise_disciplinar_data()
    
    # Prepara dados para o template
    dados_para_template = {
        'status_counts': contagem['status_counts'],
        'common_facts': contagem['common_facts'],
        'top_alunos': contagem['top_alunos']
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

# CORREÇÃO: Rota de deleção explicitamente definida
@justica_bp.route('/deletar/<int:processo_id>', methods=['POST'])
@login_required
@cal_required 
def deletar_processo(processo_id):
    success, message = JusticaService.deletar_processo(processo_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/api/alunos-por-turma/<int:turma_id>')
@login_required
def api_alunos_por_turma(turma_id):
    alunos = Aluno.query.filter_by(turma_id=turma_id).join(Aluno.user).order_by(Aluno.num_aluno).all()
    data = [{'id': a.id, 'nome': a.user.nome_completo, 'numero': a.num_aluno, 'matricula': a.user.matricula} for a in alunos]
    return jsonify(data)

@justica_bp.route('/api/alunos')
@login_required
@cal_required 
def api_get_alunos():
    search = request.args.get('q', '').lower()
    active_school = g.get('active_school')
    
    # Tratamento para usuários admin sem escola no contexto direto
    school_id_to_load = None
    if current_user.role in ['super_admin', 'programador']:
        school_id_to_load = session.get('view_as_school_id')
    elif hasattr(current_user, 'temp_active_school_id'):
        school_id_to_load = current_user.temp_active_school_id
    elif active_school:
        school_id_to_load = active_school.id

    if not school_id_to_load:
        return jsonify({'error': 'Nenhuma escola ativa.'}), 400

    query = select(Aluno).join(User).join(UserSchool).where(
        UserSchool.school_id == school_id_to_load,
        User.role == 'aluno',
        or_(User.nome_completo.ilike(f'%{search}%'), User.matricula.ilike(f'%{search}%'))
    ).limit(20)
    
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
    if not active_school:
        return redirect(url_for('justica.index'))

    try:
        locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
    except:
        pass

    if request.method == 'POST':
        processo_ids = request.form.getlist('processo_ids')
        if not processo_ids:
            flash('Nenhum processo selecionado.', 'warning')
            return redirect(url_for('justica.exportar_selecao'))

        processos = JusticaService.get_processos_por_ids([int(pid) for pid in processo_ids])
        rendered_html = render_template('justica/export_bi_template.html', processos=processos)
        
        return Response(
            rendered_html,
            mimetype="application/msword",
            headers={"Content-disposition": "attachment; filename=export_processos.doc"}
        )
    
    processos_finalizados = JusticaService.get_finalized_processos()
    return render_template('justica/exportar_selecao.html', processos=processos_finalizados)

# --- FADA (MANTIDA) ---

@justica_bp.route('/fada')
@login_required
@cal_required 
def fada_lista_alunos():
    active_school = g.get('active_school')
    if not active_school: return redirect(url_for('main.dashboard'))
    
    alunos = JusticaService.get_alunos_para_fada(active_school.id)
    return render_template('justica/fada_lista_alunos.html', alunos=alunos)

@justica_bp.route('/fada/avaliar/<int:aluno_id>', methods=['GET', 'POST'])
@login_required
@cal_required 
def fada_avaliar_aluno(aluno_id):
    active_school = g.get('active_school')
    aluno = db.session.get(Aluno, aluno_id)
    
    if not aluno:
        flash('Aluno não encontrado.', 'danger')
        return redirect(url_for('justica.fada_lista_alunos'))

    ciclos = db.session.query(Ciclo).filter_by(school_id=active_school.id).all()
    ciclo_id = request.args.get('ciclo_id', type=int) or (ciclos[-1].id if ciclos else None)
    
    dados_previa = JusticaService.calcular_previa_fada(aluno_id, ciclo_id) if ciclo_id else None
    
    default_name = current_user.nome_completo or current_user.username
    if active_school and current_user.role == 'admin_escola':
        default_name = f"Administrador {active_school.nome}"

    if request.method == 'POST':
        nome_custom = request.form.get('nome_avaliador_custom', default_name)
        success, msg, _ = JusticaService.salvar_fada(
            request.form, 
            aluno_id, 
            current_user.id, 
            nome_custom, 
            dados_calculados=None
        )
        if success:
            flash(msg, 'success')
            return redirect(url_for('justica.fada_lista_alunos'))
        else:
            flash(msg, 'danger')

    return render_template(
        'justica/fada_formulario.html', 
        aluno=aluno, 
        ciclos=ciclos, 
        ciclo_atual=ciclo_id, 
        dados_previa=dados_previa,
        default_name=default_name
    )

@justica_bp.route('/fada/pdf/<int:avaliacao_id>')
@login_required
@cal_required 
def fada_gerar_pdf(avaliacao_id):
    avaliacao = JusticaService.get_fada_por_id(avaliacao_id)
    if not avaliacao:
        flash('Avaliação não encontrada.', 'danger')
        return redirect(url_for('justica.fada_lista_alunos'))

    try:
        data_geracao = datetime.now(ZoneInfo("America/Sao_Paulo"))
    except:
        data_geracao = datetime.now()

    html = render_template(
        'justica/fada_pdf_template.html', 
        avaliacao=avaliacao, 
        aluno=avaliacao.aluno, 
        avaliador_nome=avaliacao.nome_avaliador_custom,
        data_geracao=data_geracao
    )
    pdf = HTML(string=html).write_pdf()
    return Response(
        pdf, 
        mimetype='application/pdf',
        headers={"Content-disposition": f"attachment; filename=fada_aluno_{avaliacao.aluno_id}.pdf"}
    )