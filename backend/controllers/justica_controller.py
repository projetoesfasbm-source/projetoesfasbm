import logging
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, Response, g, session
from flask_login import login_required, current_user
from sqlalchemy import select
from datetime import datetime
from weasyprint import HTML

from ..models.database import db
from ..models.aluno import Aluno
from ..models.user import User
from ..models.turma import Turma
from ..models.processo_disciplina import StatusProcesso, ProcessoDisciplina
from ..models.discipline_rule import DisciplineRule
from ..models.elogio import Elogio
from ..models.ciclo import Ciclo
from ..services.justica_service import JusticaService
from utils.decorators import cal_required

logger = logging.getLogger(__name__)
justica_bp = Blueprint('justica', __name__, url_prefix='/justica-e-disciplina')

def _get_current_school_id():
    """Recupera ID da escola de forma segura (Int ou None)."""
    try:
        # 1. Global
        if g.get('active_school') and hasattr(g.active_school, 'id'):
            return int(g.active_school.id)
        # 2. Sessão
        sid = session.get('active_school_id')
        if sid: return int(sid)
        # 3. Fallback Admin/Gestor (Cadastro do Usuário)
        if hasattr(current_user, 'school_id') and current_user.school_id:
            return int(current_user.school_id)
        # 4. Fallback Aluno
        if getattr(current_user, 'role', '') == 'aluno':
            if getattr(current_user, 'aluno_profile', None) and current_user.aluno_profile.turma:
                return int(current_user.aluno_profile.turma.school_id)
    except: return None
    return None

@justica_bp.route('/')
@login_required
def index():
    # Inicializa variáveis para evitar erro de referência (UnboundLocalError)
    em, fin, regras, turmas = [], [], [], []
    permite_pontuacao = False
    school_id = None

    try:
        school_id = _get_current_school_id()
        active_school = g.get('active_school')

        # Busca processos
        processos = JusticaService.get_processos_para_usuario(current_user, school_id_override=school_id)
        
        # Filtra listas (usando string para evitar erro de Enum)
        # Verifica se 'status' existe e converte para string antes de comparar
        em = [p for p in processos if str(getattr(p, 'status', '')) != 'Finalizado']
        fin = [p for p in processos if str(getattr(p, 'status', '')) == 'Finalizado']
        
        if school_id:
            if active_school:
                permite_pontuacao, _ = JusticaService.get_pontuacao_config(active_school)
                regras = db.session.scalars(select(DisciplineRule).where(DisciplineRule.npccal_type == active_school.npccal_type).order_by(DisciplineRule.codigo)).all()
            else:
                regras = db.session.scalars(select(DisciplineRule).where(DisciplineRule.school_id == school_id).order_by(DisciplineRule.codigo)).all()
            
            # Carrega turmas da escola
            turmas = db.session.scalars(select(Turma).where(Turma.school_id == school_id).order_by(Turma.nome)).all()
        else:
            # Fallback Admin Global (vê tudo para não travar a tela)
            if current_user.role in ['admin', 'super_admin', 'master']:
                turmas = db.session.scalars(select(Turma).order_by(Turma.nome)).all()
                regras = db.session.scalars(select(DisciplineRule).limit(50)).all()

    except Exception as e:
        logger.exception("Erro crítico no index justiça")
        flash("Erro ao carregar dados. Tente recarregar a página.", 'danger')
        # Em caso de erro, turmas e regras estarão vazios, mas a página carrega.

    atributos = [(i, nome) for i, nome in enumerate(['Expressão', 'Planejamento', 'Perseverança', 'Apresentação', 'Lealdade', 'Tato', 'Equilíbrio', 'Disciplina', 'Responsabilidade', 'Maturidade', 'Assiduidade', 'Pontualidade', 'Dicção', 'Liderança', 'Relacionamento', 'Ética', 'Produtividade', 'Eficiência'], 1)]

    return render_template(
        'justica/index.html', 
        em_andamento=em, 
        finalizados=fin, 
        fatos_predefinidos=regras, 
        turmas=turmas, 
        permite_pontuacao=permite_pontuacao, 
        atributos_fada=atributos, 
        hoje=datetime.today().strftime('%Y-%m-%d')
    )

@justica_bp.route('/api/alunos-por-turma/<int:turma_id>')
@login_required
def api_alunos_por_turma(turma_id):
    try:
        user_school_id = _get_current_school_id()
        turma = db.session.get(Turma, turma_id)
        
        if not turma:
            return jsonify([])

        # LÓGICA DE PERMISSÃO (CORRIGIDA)
        permitido = False
        
        # 1. Super Usuários
        if current_user.role in ['super_admin', 'master']:
            permitido = True
        
        # 2. Admin/Gestor da Escola (Validação por ID)
        elif user_school_id is not None and int(turma.school_id) == int(user_school_id):
            permitido = True
            
        # 3. Admin sem contexto (Fallback para evitar bloqueio indevido)
        elif user_school_id is None and current_user.role == 'admin':
            permitido = True

        if not permitido:
            logger.warning(f"API Bloqueada: User {current_user.id} (Escola {user_school_id}) tentou Turma {turma.id} (Escola {turma.school_id})")
            return jsonify([])

        # Busca alunos (ORM Padrão - Agora seguro com Model corrigido)
        query = select(Aluno).where(Aluno.turma_id == turma_id).join(User).order_by(Aluno.num_aluno)
        alunos = db.session.scalars(query).all()
        
        return jsonify([{'id': a.id, 'nome': a.user.nome_completo, 'numero': a.num_aluno} for a in alunos])
        
    except Exception as e:
        logger.exception(f"Erro API Turma {turma_id}")
        return jsonify([])

# --- DEMAIS ROTAS (Essenciais para o funcionamento) ---

@justica_bp.route('/registrar-em-massa', methods=['POST'])
@login_required
@cal_required 
def registrar_em_massa():
    try:
        school = g.get('active_school')
        ids = request.form.getlist('alunos_selecionados') or ([request.form.get('aluno_id')] if request.form.get('aluno_id') else [])
        if not ids: return redirect(url_for('justica.index'))

        dt_str = request.form.get('data_fato')
        desc = request.form.get('descricao') or request.form.get('fato_descricao')
        usa_pontuacao, _ = JusticaService.get_pontuacao_config(school)
        tipo = request.form.get('tipo_registro')

        count = 0
        if tipo == 'infracao':
            regra_id = request.form.get('regra_id')
            pts, cod, r_fk = 0.0, None, None
            if regra_id:
                r = db.session.get(DisciplineRule, int(regra_id))
                if r: pts, cod, r_fk = (r.pontos if usa_pontuacao else 0.0), r.codigo, r.id
            if not r_fk and request.form.get('fato_pontos') and usa_pontuacao:
                try: pts = float(request.form.get('fato_pontos'))
                except: pass
            
            obs = request.form.get('observacao', '')
            for aid in ids:
                JusticaService.criar_processo(desc, obs, int(aid), current_user.id, pts, cod, r_fk, dt_str)
                count += 1
            flash(f'{count} infrações registradas.', 'success')
        
        elif tipo == 'elogio':
            a1, a2 = request.form.get('atributo_1'), request.form.get('atributo_2')
            pts = 0.5 if (a1 or a2) and usa_pontuacao else 0.0
            dt = JusticaService._ensure_datetime(dt_str)
            for aid in ids:
                db.session.add(Elogio(aluno_id=int(aid), registrado_por_id=current_user.id, data_elogio=dt, descricao=desc, pontos=pts, atributo_1=int(a1) if a1 else None, atributo_2=int(a2) if a2 else None))
                count += 1
            db.session.commit()
            flash(f'{count} elogios.', 'success')
        else:
            for aid in ids:
                JusticaService.criar_processo(desc, request.form.get('observacao', ''), int(aid), current_user.id, 0.0, None, None, dt_str)
                count += 1
            flash(f'{count} registros.', 'success')
    except:
        db.session.rollback()
        flash('Erro ao registrar.', 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/novo', methods=['POST'])
@login_required
def novo_processo(): return registrar_em_massa()

@justica_bp.route('/analise')
@login_required
@cal_required 
def analise():
    try: return render_template('justica/analise.html', dados=JusticaService.get_analise_disciplinar_data(_get_current_school_id()))
    except: return redirect(url_for('justica.index'))

@justica_bp.route('/finalizar/<int:pid>', methods=['POST'])
@login_required
def finalizar_processo(pid):
    ok, msg = JusticaService.finalizar_processo(pid, request.form.get('decisao_final'), request.form.get('fundamentacao'), request.form.get('detalhes_sancao'), request.form.get('turnos_sustacao'))
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/deletar/<int:pid>', methods=['POST'])
@login_required
def deletar_processo(pid):
    ok, msg = JusticaService.deletar_processo(pid)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/dar-ciente/<int:pid>', methods=['POST'])
@login_required
def dar_ciente(pid):
    ok, msg = JusticaService.registrar_ciente(pid, current_user)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/enviar-defesa/<int:pid>', methods=['POST'])
@login_required
def enviar_defesa(pid):
    ok, msg = JusticaService.enviar_defesa(pid, request.form.get('defesa'), current_user)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/api/alunos')
@login_required
def api_get_alunos():
    sid = _get_current_school_id()
    q = request.args.get('q', '').lower()
    query = select(Aluno).join(User).join(Turma)
    if sid: query = query.where(Turma.school_id == sid)
    query = query.where(User.nome_completo.ilike(f'%{q}%')).limit(20)
    return jsonify([{'id': a.id, 'text': a.user.nome_completo} for a in db.session.scalars(query).all()])

@justica_bp.route('/api/aluno-details/<int:aluno_id>')
@login_required
def api_get_aluno_details(aluno_id):
    sid = _get_current_school_id()
    a = db.session.get(Aluno, aluno_id)
    if not a: return jsonify({'error': '404'}), 404
    if sid and a.turma and int(a.turma.school_id) != int(sid):
        if current_user.role not in ['super_admin', 'master', 'admin']: return jsonify({'error': '403'}), 403
    return jsonify({'nome_completo': a.user.nome_completo, 'matricula': a.user.matricula, 'posto_graduacao': a.user.posto_graduacao})

@justica_bp.route('/exportar', methods=['GET', 'POST'])
@login_required
def exportar_selecao():
    sid = _get_current_school_id()
    if request.method == 'POST':
        ids = [int(i) for i in request.form.getlist('processo_ids')]
        return Response(render_template('justica/export_bi_template.html', processos=JusticaService.get_processos_por_ids(ids, sid)), mimetype="application/msword", headers={"Content-disposition": "attachment; filename=export.doc"})
    return render_template('justica/exportar_selecao.html', processos=JusticaService.get_finalized_processos(sid))

@justica_bp.route('/fada')
@login_required
def fada_lista_alunos(): return render_template('justica/fada_lista_alunos.html', alunos=JusticaService.get_alunos_para_fada(_get_current_school_id()))

@justica_bp.route('/fada/avaliar/<int:aluno_id>', methods=['GET', 'POST'])
@login_required
def fada_avaliar_aluno(aluno_id):
    try:
        sid = _get_current_school_id()
        aluno = db.session.get(Aluno, aluno_id)
        if not aluno: return redirect(url_for('justica.fada_lista_alunos'))
        
        if sid and aluno.turma and int(aluno.turma.school_id) != int(sid):
             if current_user.role not in ['super_admin', 'master', 'admin']:
                flash('Acesso negado', 'danger')
                return redirect(url_for('justica.fada_lista_alunos'))

        cid = request.args.get('ciclo_id', type=int)
        ciclos = db.session.scalars(select(Ciclo).where(Ciclo.school_id == (aluno.turma.school_id if aluno.turma else None))).all()
        if not cid and ciclos: cid = ciclos[-1].id

        if request.method == 'POST':
            ok, msg, aid = JusticaService.salvar_fada(request.form, aluno_id, current_user.id, request.form.get('nome_avaliador_custom', current_user.nome_completo))
            if ok: return redirect(url_for('justica.fada_gerar_pdf', avaliacao_id=aid))
            flash(msg, 'danger')

        return render_template('justica/fada_formulario.html', aluno=aluno, ciclos=ciclos, ciclo_atual=cid, dados_previa=JusticaService.calcular_previa_fada(aluno_id, cid), default_name=current_user.nome_completo)
    except: return redirect(url_for('justica.fada_lista_alunos'))

@justica_bp.route('/fada/pdf/<int:avid>')
@login_required
def fada_gerar_pdf(avid):
    av = JusticaService.get_fada_por_id(avid)
    if not av: return "404", 404
    return Response(HTML(string=render_template('justica/fada_pdf_template.html', avaliacao=av, aluno=av.aluno, data_geracao=datetime.now())).write_pdf(), mimetype='application/pdf')