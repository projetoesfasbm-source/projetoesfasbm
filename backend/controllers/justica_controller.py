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
from ..models.elogio import Elogio
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
    
    if not alunos_ids:
        # Tenta pegar aluno único do form antigo se vier vazio
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

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao registrar: {str(e)}', 'danger')

    return redirect(url_for('justica.index'))

# --- ROTAS DE SUPORTE E ANÁLISE (MANTIDAS) ---

@justica_bp.route('/analise')
@login_required
@cal_required 
def analise():
    active_school = g.get('active_school')
    if not active_school or not active_school.npccal_type in ['cspm', 'cbfpm', 'ctsp']:
        flash('A Análise de Dados não se aplica a esta escola.', 'info')
        return redirect(url_for('justica.index'))

    contagem = JusticaService.get_analise_disciplinar_data()
    return render_template('justica/analise.html', dados=contagem)

@justica_bp.route('/finalizar/<int:processo_id>', methods=['POST'])
@login_required
@cal_required 
def finalizar_processo(processo_id):
    decisao = request.form.get('decisao_final')
    fundamentacao = request.form.get('fundamentacao')
    detalhes = request.form.get('detalhes_sancao')
    success, message = JusticaService.finalizar_processo(processo_id, decisao, fundamentacao, detalhes)
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
    success, message = JusticaService.enviar_defesa(processo_id, defesa, current_user)
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
    if not active_school: return jsonify([])

    query = select(Aluno).join(User).join(UserSchool).where(
        UserSchool.school_id == active_school.id,
        User.role == 'aluno',
        or_(User.nome_completo.ilike(f'%{search}%'), User.matricula.ilike(f'%{search}%'))
    ).limit(20)
    
    alunos = db.session.scalars(query).all()
    return jsonify([{'id': a.id, 'text': f"{a.user.nome_completo} ({a.user.matricula})"} for a in alunos])
    
@justica_bp.route('/api/aluno-details/<int:aluno_id>')
@login_required
@cal_required 
def api_get_aluno_details(aluno_id):
    aluno = db.session.get(Aluno, aluno_id)
    if not aluno: return jsonify({'error': 'Not found'}), 404
    return jsonify({
        'nome_completo': aluno.user.nome_completo,
        'matricula': aluno.user.matricula,
        'posto_graduacao': aluno.user.posto_graduacao
    })

@justica_bp.route('/exportar', methods=['GET', 'POST'])
@login_required
@cal_required 
def exportar_selecao():
    if request.method == 'POST':
        processo_ids = request.form.getlist('processo_ids')
        processos = JusticaService.get_processos_por_ids([int(pid) for pid in processo_ids])
        rendered_html = render_template('justica/export_bi_template.html', processos=processos)
        return Response(rendered_html, mimetype="application/msword", headers={"Content-disposition": "attachment; filename=export_processos.doc"})
    
    processos_finalizados = JusticaService.get_finalized_processos()
    return render_template('justica/exportar_selecao.html', processos=processos_finalizados)

@justica_bp.route('/fada')
@login_required
@cal_required 
def fada_lista_alunos():
    active_school = g.get('active_school')
    alunos = JusticaService.get_alunos_para_fada(active_school.id)
    return render_template('justica/fada_lista_alunos.html', alunos=alunos)

@justica_bp.route('/fada/avaliar/<int:aluno_id>', methods=['GET', 'POST'])
@login_required
@cal_required 
def fada_avaliar_aluno(aluno_id):
    aluno = db.session.get(Aluno, aluno_id)
    ciclos = db.session.query(Ciclo).filter_by(school_id=g.active_school.id).all()
    ciclo_id = request.args.get('ciclo_id', type=int) or (ciclos[-1].id if ciclos else None)
    
    dados_previa = JusticaService.calcular_previa_fada(aluno_id, ciclo_id) if ciclo_id else None

    if request.method == 'POST':
        JusticaService.salvar_fada(request.form, aluno_id, current_user.id, request.form.get('nome_avaliador'), dados_calculados=None)
        return redirect(url_for('justica.fada_lista_alunos'))

    return render_template('justica/fada_formulario.html', aluno=aluno, ciclos=ciclos, dados_previa=dados_previa)

@justica_bp.route('/fada/pdf/<int:avaliacao_id>')
@login_required
@cal_required 
def fada_gerar_pdf(avaliacao_id):
    avaliacao = JusticaService.get_fada_por_id(avaliacao_id)
    html = render_template('justica/fada_pdf_template.html', avaliacao=avaliacao, aluno=avaliacao.aluno, data_geracao=datetime.now())
    pdf = HTML(string=html).write_pdf()
    return Response(pdf, mimetype='application/pdf')