from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, Response, g, session
from flask_login import login_required, current_user
from sqlalchemy import select, or_
from datetime import datetime
from weasyprint import HTML
import locale

# --- IMPORTAÇÕES DOS MODELOS (CRÍTICO PARA EVITAR ERRO 500) ---
from ..models.database import db
from ..models.aluno import Aluno
from ..models.turma import Turma
from ..models.discipline_rule import DisciplineRule
from ..models.processo_disciplina import ProcessoDisciplina
from ..models.elogio import Elogio          # Necessário para registrar elogios
from ..models.ciclo import Ciclo            # Necessário para a FADA
from ..models.fada_avaliacao import FadaAvaliacao # Necessário para a FADA
from ..services.justica_service import JusticaService
from utils.decorators import cal_required

# Tenta configurar timezone
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

justica_bp = Blueprint('justica', __name__, url_prefix='/justica-e-disciplina')

@justica_bp.route('/')
@login_required
def index():
    """Página principal de Justiça e Disciplina."""
    # Busca processos
    processos = JusticaService.get_processos_para_usuario(current_user)
    
    em_andamento = [p for p in processos if p.status != 'Finalizado']
    finalizados = [p for p in processos if p.status == 'Finalizado']

    active_school = g.get('active_school')
    fatos_predefinidos = []
    turmas = []
    permite_pontuacao = False

    if active_school:
        permite_pontuacao = active_school.npccal_type in ['cspm', 'cbfpm']
        
        # Carrega regras ordenadas pelo código
        fatos_predefinidos = db.session.scalars(
            select(DisciplineRule)
            .where(DisciplineRule.npccal_type == active_school.npccal_type)
            .order_by(DisciplineRule.codigo)
        ).all()
        
        # Carrega turmas
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
        em_andamento=em_andamento,
        finalizados=finalizados,
        fatos_predefinidos=fatos_predefinidos,
        turmas=turmas,
        permite_pontuacao=permite_pontuacao,
        atributos_fada=atributos_fada,
        hoje=datetime.today().strftime('%Y-%m-%d')
    )

@justica_bp.route('/registrar-em-massa', methods=['POST'])
@login_required
@cal_required 
def registrar_em_massa():
    active_school = g.get('active_school')
    tipo = request.form.get('tipo_registro')
    alunos_ids = request.form.getlist('alunos_selecionados')
    
    # Fallback para formulário antigo (individual)
    if not alunos_ids:
        indiv = request.form.get('aluno_id')
        if indiv: alunos_ids = [indiv]

    if not alunos_ids:
        flash('Nenhum aluno selecionado.', 'warning')
        return redirect(url_for('justica.index'))

    data_str = request.form.get('data_fato')
    dt = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else datetime.now().date()
    desc = request.form.get('descricao') or request.form.get('fato_descricao')
    
    count = 0
    try:
        # REGISTRO DE INFRAÇÃO
        if tipo == 'infracao':
            regra_id = request.form.get('regra_id')
            pontos = float(request.form.get('fato_pontos') or 0.0)
            cod = None
            
            if regra_id:
                r = db.session.get(DisciplineRule, regra_id)
                if r: 
                    pontos = r.pontos
                    cod = r.codigo
            
            obs = request.form.get('observacao', '')
            for aid in alunos_ids:
                JusticaService.criar_processo(desc, obs, int(aid), current_user.id, pontos, cod, dt)
                count += 1
            flash(f'{count} infrações registradas com sucesso.', 'success')

        # REGISTRO DE ELOGIO
        elif tipo == 'elogio':
            a1 = request.form.get('atributo_1')
            a2 = request.form.get('atributo_2')
            pts = 0.5 if (a1 or a2) and active_school.npccal_type in ['cbfpm', 'cspm'] else 0.0
            
            for aid in alunos_ids:
                ne = Elogio(
                    aluno_id=int(aid), registrado_por_id=current_user.id,
                    data_elogio=dt, descricao=desc, pontos=pts,
                    atributo_1=int(a1) if a1 else None, atributo_2=int(a2) if a2 else None
                )
                db.session.add(ne)
                count += 1
            db.session.commit()
            flash(f'{count} elogios registrados com sucesso.', 'success')
            
        else:
            # Fallback genérico
            obs = request.form.get('observacao', '')
            for aid in alunos_ids:
                JusticaService.criar_processo(desc, obs, int(aid), current_user.id, 0.0, None, dt)
                count += 1
            flash(f'{count} registros criados.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao registrar: {e}', 'danger')

    return redirect(url_for('justica.index'))

# Rota legado para compatibilidade
@justica_bp.route('/novo', methods=['POST'])
@login_required
@cal_required
def novo_processo():
    return registrar_em_massa()

# --- ANÁLISE (DASHBOARD) ---
@justica_bp.route('/analise')
@login_required
@cal_required 
def analise():
    # O Service agora retorna dicionários seguros, evitando erro no template
    dados = JusticaService.get_analise_disciplinar_data()
    return render_template('justica/analise.html', dados=dados)

# --- AÇÕES EM PROCESSOS ---
@justica_bp.route('/finalizar/<int:processo_id>', methods=['POST'])
@login_required
@cal_required 
def finalizar_processo(processo_id):
    decisao = request.form.get('decisao_final')
    fund = request.form.get('fundamentacao')
    detalhes = request.form.get('detalhes_sancao')
    sus = request.form.get('turnos_sustacao')
    if sus and decisao == 'Sustação da Dispensa': detalhes = f"Sustação: {sus}"
    
    ok, msg = JusticaService.finalizar_processo(processo_id, decisao, fund, detalhes)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/deletar/<int:processo_id>', methods=['POST'])
@login_required
@cal_required 
def deletar_processo(processo_id):
    ok, msg = JusticaService.deletar_processo(processo_id)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/dar-ciente/<int:processo_id>', methods=['POST'])
@login_required
def dar_ciente(processo_id):
    ok, msg = JusticaService.registrar_ciente(processo_id, current_user)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/enviar-defesa/<int:processo_id>', methods=['POST'])
@login_required
def enviar_defesa(processo_id):
    texto = request.form.get('defesa')
    ok, msg = JusticaService.enviar_defesa(processo_id, texto, current_user)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('justica.index'))

# --- API JSON ---
@justica_bp.route('/api/alunos-por-turma/<int:turma_id>')
@login_required
def api_alunos_por_turma(turma_id):
    alunos = db.session.scalars(select(Aluno).where(Aluno.turma_id == turma_id).join(User).order_by(Aluno.num_aluno)).all()
    return jsonify([{'id': a.id, 'nome': a.user.nome_completo, 'numero': a.num_aluno} for a in alunos])

@justica_bp.route('/api/aluno-details/<int:aluno_id>')
@login_required
def api_get_aluno_details(aluno_id):
    a = db.session.get(Aluno, aluno_id)
    if not a: return jsonify({'error': '404'}), 404
    return jsonify({'nome_completo': a.user.nome_completo, 'matricula': a.user.matricula, 'posto_graduacao': a.user.posto_graduacao})

@justica_bp.route('/api/alunos')
@login_required
def api_get_alunos():
    search = request.args.get('q', '').lower()
    school = g.get('active_school')
    if not school: return jsonify([])
    alunos = db.session.scalars(select(Aluno).join(User).join(UserSchool).where(UserSchool.school_id==school.id, User.role=='aluno', User.nome_completo.ilike(f'%{search}%')).limit(20)).all()
    return jsonify([{'id': a.id, 'text': a.user.nome_completo} for a in alunos])

@justica_bp.route('/exportar', methods=['GET', 'POST'])
@login_required
@cal_required 
def exportar_selecao():
    if request.method == 'POST':
        ids = request.form.getlist('processo_ids')
        procs = JusticaService.get_processos_por_ids([int(i) for i in ids])
        return Response(render_template('justica/export_bi_template.html', processos=procs), 
                       mimetype="application/msword", 
                       headers={"Content-disposition": "attachment; filename=export.doc"})
    return render_template('justica/exportar_selecao.html', processos=JusticaService.get_finalized_processos())

# --- FADA (AVALIAÇÃO ATITUDINAL) ---
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
        flash('Aluno não encontrado', 'danger')
        return redirect(url_for('justica.fada_lista_alunos'))

    # Carrega ciclos para o dropdown (ESSENCIAL PARA EVITAR ERRO)
    ciclos = db.session.scalars(select(Ciclo).where(Ciclo.school_id == active_school.id)).all()
    
    # Define ciclo atual
    ciclo_id = request.args.get('ciclo_id', type=int)
    if not ciclo_id and ciclos:
        ciclo_id = ciclos[-1].id

    # Calcula prévia
    dados_previa = None
    if ciclo_id:
        dados_previa = JusticaService.calcular_previa_fada(aluno_id, ciclo_id)

    default_name = current_user.nome_completo or "Avaliador"

    if request.method == 'POST':
        nome = request.form.get('nome_avaliador_custom', default_name)
        ok, msg, av_id = JusticaService.salvar_fada(request.form, aluno_id, current_user.id, nome, dados_calculados=None)
        if ok:
            flash(msg, 'success')
            return redirect(url_for('justica.fada_gerar_pdf', avaliacao_id=av_id)) # Redireciona para PDF após salvar
        else:
            flash(msg, 'danger')

    return render_template('justica/fada_formulario.html', 
                           aluno=aluno, 
                           ciclos=ciclos, 
                           ciclo_atual=ciclo_id, 
                           dados_previa=dados_previa, 
                           default_name=default_name)

@justica_bp.route('/fada/pdf/<int:avaliacao_id>')
@login_required
@cal_required 
def fada_gerar_pdf(avaliacao_id):
    av = JusticaService.get_fada_por_id(avaliacao_id)
    if not av:
        flash('Avaliação não encontrada.', 'danger')
        return redirect(url_for('justica.fada_lista_alunos'))

    html = render_template('justica/fada_pdf_template.html', avaliacao=av, aluno=av.aluno, data_geracao=datetime.now())
    return Response(HTML(string=html).write_pdf(), mimetype='application/pdf')