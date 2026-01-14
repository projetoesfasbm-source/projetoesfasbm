import logging
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, Response, g
from flask_login import login_required, current_user
from sqlalchemy import select
from datetime import datetime
from weasyprint import HTML

from ..models.database import db
from ..models.aluno import Aluno
from ..models.turma import Turma
from ..models.processo_disciplina import StatusProcesso
from ..models.discipline_rule import DisciplineRule
from ..models.elogio import Elogio
from ..models.ciclo import Ciclo
from ..services.justica_service import JusticaService
from utils.decorators import cal_required

logger = logging.getLogger(__name__)
justica_bp = Blueprint('justica', __name__, url_prefix='/justica-e-disciplina')

@justica_bp.route('/')
@login_required
def index():
    try:
        active_school = g.get('active_school')
        school_id = active_school.id if active_school else None
        
        processos = JusticaService.get_processos_para_usuario(current_user, school_id_override=school_id)
        
        em = [p for p in processos if p.status != StatusProcesso.FINALIZADO]
        fin = [p for p in processos if p.status == StatusProcesso.FINALIZADO]
        
        regras = []
        turmas = []
        permite_pontuacao, _ = JusticaService.get_pontuacao_config(active_school)
        
        if active_school:
            regras = db.session.scalars(
                select(DisciplineRule)
                .where(DisciplineRule.npccal_type == active_school.npccal_type)
                .order_by(DisciplineRule.codigo)
            ).all()
            turmas = db.session.scalars(select(Turma).where(Turma.school_id == school_id).order_by(Turma.nome)).all()

        atributos = [(i, nome) for i, nome in enumerate([
            'Expressão', 'Planejamento', 'Perseverança', 'Apresentação', 'Lealdade', 'Tato', 
            'Equilíbrio', 'Disciplina', 'Responsabilidade', 'Maturidade', 'Assiduidade', 
            'Pontualidade', 'Dicção', 'Liderança', 'Relacionamento', 'Ética', 'Produtividade', 'Eficiência'
        ], start=1)]

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
    except Exception as e:
        logger.exception("Erro ao carregar painel de justiça")
        flash("Ocorreu um erro ao carregar o painel.", 'danger')
        return render_template('base.html')

@justica_bp.route('/registrar-em-massa', methods=['POST'])
@login_required
@cal_required 
def registrar_em_massa():
    try:
        school = g.get('active_school')
        tipo = request.form.get('tipo_registro')
        ids = request.form.getlist('alunos_selecionados') or ([request.form.get('aluno_id')] if request.form.get('aluno_id') else [])
        
        if not ids:
            flash('Nenhum aluno selecionado.', 'warning')
            return redirect(url_for('justica.index'))

        dt_str = request.form.get('data_fato')
        desc = request.form.get('descricao') or request.form.get('fato_descricao')
        usa_pontuacao, valor_elogio = JusticaService.get_pontuacao_config(school)

        count = 0
        if tipo == 'infracao':
            regra_id_str = request.form.get('regra_id')
            pts = 0.0
            cod = None
            regra_fk = None
            
            if regra_id_str:
                r = db.session.get(DisciplineRule, int(regra_id_str))
                if r: 
                    pts = r.pontos if usa_pontuacao else 0.0
                    cod = r.codigo
                    regra_fk = r.id
            
            if not regra_fk and request.form.get('fato_pontos') and usa_pontuacao:
                try: pts = float(request.form.get('fato_pontos'))
                except: pass

            obs = request.form.get('observacao', '')
            for aid in ids:
                JusticaService.criar_processo(
                    descricao=desc, 
                    observacao=obs, 
                    aluno_id=int(aid), 
                    autor_id=current_user.id, 
                    pontos=pts, 
                    codigo_infracao=cod, 
                    regra_id=regra_fk,
                    data_ocorrencia=dt_str
                )
                count += 1
            flash(f'{count} infrações registradas.', 'success')

        elif tipo == 'elogio':
            a1, a2 = request.form.get('atributo_1'), request.form.get('atributo_2')
            pts = valor_elogio if (a1 or a2) and usa_pontuacao else 0.0
            dt_obj = JusticaService._ensure_datetime(dt_str)
            
            for aid in ids:
                elogio = Elogio(
                    aluno_id=int(aid), 
                    registrado_por_id=current_user.id, 
                    data_elogio=dt_obj, 
                    descricao=desc, 
                    pontos=pts, 
                    atributo_1=int(a1) if a1 else None, 
                    atributo_2=int(a2) if a2 else None
                )
                db.session.add(elogio)
                count += 1
            db.session.commit()
            flash(f'{count} elogios registrados.', 'success')
        
        else:
            obs = request.form.get('observacao', '')
            for aid in ids:
                JusticaService.criar_processo(desc, obs, int(aid), current_user.id, 0.0, None, None, dt_str)
                count += 1
            flash(f'{count} registros criados.', 'success')

    except Exception as e:
        db.session.rollback()
        logger.exception("Erro ao registrar em massa")
        flash('Erro ao processar registro.', 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/novo', methods=['POST'])
@login_required
def novo_processo(): return registrar_em_massa()

@justica_bp.route('/analise')
@login_required
@cal_required 
def analise():
    try:
        s = g.get('active_school')
        dados = JusticaService.get_analise_disciplinar_data(s.id if s else None)
        return render_template('justica/analise.html', dados=dados)
    except Exception as e:
        logger.exception("Erro no dashboard de análise")
        flash("Erro ao carregar análise.", "danger")
        return redirect(url_for('justica.index'))

@justica_bp.route('/finalizar/<int:processo_id>', methods=['POST'])
@login_required
def finalizar_processo(processo_id):
    decisao = request.form.get('decisao_final')
    fund = request.form.get('fundamentacao')
    det = request.form.get('detalhes_sancao')
    sus = request.form.get('turnos_sustacao')
    
    ok, msg = JusticaService.finalizar_processo(processo_id, decisao, fund, det, sus)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/deletar/<int:processo_id>', methods=['POST'])
@login_required
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
    ok, msg = JusticaService.enviar_defesa(processo_id, request.form.get('defesa'), current_user)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/api/alunos')
@login_required
def api_get_alunos():
    s = g.get('active_school')
    if not s: return jsonify([])
    q = request.args.get('q', '').lower()
    return jsonify([{'id': a.id, 'text': a.user.nome_completo} for a in db.session.scalars(select(Aluno).join(User).join(Turma).where(Turma.school_id==s.id, User.role=='aluno', User.nome_completo.ilike(f'%{q}%')).limit(20)).all()])

@justica_bp.route('/api/alunos-por-turma/<int:turma_id>')
@login_required
def api_alunos_por_turma(turma_id):
    s = g.get('active_school')
    if not s: return jsonify([])
    
    turma = db.session.get(Turma, turma_id)
    if not turma or turma.school_id != s.id:
        return jsonify([]) 

    return jsonify([{'id': a.id, 'nome': a.user.nome_completo, 'numero': a.num_aluno} for a in db.session.scalars(select(Aluno).where(Aluno.turma_id == turma_id).join(User).order_by(Aluno.num_aluno)).all()])

@justica_bp.route('/api/aluno-details/<int:aluno_id>')
@login_required
def api_get_aluno_details(aluno_id):
    a = db.session.get(Aluno, aluno_id)
    if not a: return jsonify({'error': '404'}), 404
    return jsonify({'nome_completo': a.user.nome_completo, 'matricula': a.user.matricula, 'posto_graduacao': a.user.posto_graduacao})

@justica_bp.route('/exportar', methods=['GET', 'POST'])
@login_required
def exportar_selecao():
    school = g.get('active_school')
    sid = school.id if school else None

    if request.method == 'POST':
        ids = request.form.getlist('processo_ids')
        ids_int = [int(i) for i in ids]
        processos = JusticaService.get_processos_por_ids(ids_int, sid)
        return Response(render_template('justica/export_bi_template.html', processos=processos), mimetype="application/msword", headers={"Content-disposition": "attachment; filename=export.doc"})
    
    lista = JusticaService.get_finalized_processos(sid)
    return render_template('justica/exportar_selecao.html', processos=lista)

@justica_bp.route('/fada')
@login_required
def fada_lista_alunos():
    s = g.get('active_school')
    if not s: return redirect(url_for('main.dashboard'))
    return render_template('justica/fada_lista_alunos.html', alunos=JusticaService.get_alunos_para_fada(s.id))

@justica_bp.route('/fada/avaliar/<int:aluno_id>', methods=['GET', 'POST'])
@login_required
def fada_avaliar_aluno(aluno_id):
    try:
        s = g.get('active_school')
        aluno = db.session.get(Aluno, aluno_id)
        
        if not aluno or not aluno.turma or aluno.turma.school_id != s.id:
            flash('Aluno não encontrado ou não pertence a esta escola', 'danger')
            return redirect(url_for('justica.fada_lista_alunos'))

        ciclos = []
        try: ciclos = db.session.scalars(select(Ciclo).where(Ciclo.school_id == s.id)).all()
        except: pass

        cid = request.args.get('ciclo_id', type=int)
        if not cid and ciclos: cid = ciclos[-1].id

        previa = JusticaService.calcular_previa_fada(aluno_id, cid) if cid else None
        nome_padrao = current_user.nome_completo or "Avaliador"

        if request.method == 'POST':
            ok, msg, av_id = JusticaService.salvar_fada(
                request.form, 
                aluno_id, 
                current_user.id, 
                request.form.get('nome_avaliador_custom', nome_padrao)
            )
            if ok:
                flash(msg, 'success')
                return redirect(url_for('justica.fada_gerar_pdf', avaliacao_id=av_id))
            else: flash(msg, 'danger')

        return render_template('justica/fada_formulario.html', aluno=aluno, ciclos=ciclos, ciclo_atual=cid, dados_previa=previa, default_name=nome_padrao)
    except Exception as e:
        logger.exception("Erro ao abrir formulário FADA")
        flash(f"Erro ao abrir avaliação", 'danger')
        return redirect(url_for('justica.fada_lista_alunos'))

@justica_bp.route('/fada/pdf/<int:avaliacao_id>')
@login_required
def fada_gerar_pdf(avaliacao_id):
    try:
        av = JusticaService.get_fada_por_id(avaliacao_id)
        if not av: return "Não encontrado", 404
        html = render_template('justica/fada_pdf_template.html', avaliacao=av, aluno=av.aluno, data_geracao=datetime.now())
        return Response(HTML(string=html).write_pdf(), mimetype='application/pdf')
    except Exception as e:
        logger.exception("Erro ao gerar PDF FADA")
        return f"Erro interno ao gerar PDF", 500