from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, Response, g, session
from flask_login import login_required, current_user
from sqlalchemy import select, or_
from datetime import datetime
from weasyprint import HTML
import locale
import traceback 

from ..models.database import db
from ..models.aluno import Aluno
from ..models.turma import Turma
from ..models.discipline_rule import DisciplineRule
from ..models.processo_disciplina import ProcessoDisciplina
from ..models.elogio import Elogio
from ..models.ciclo import Ciclo
from ..models.fada_avaliacao import FadaAvaliacao
from ..services.justica_service import JusticaService
from utils.decorators import cal_required

try: from zoneinfo import ZoneInfo
except ImportError: from backports.zoneinfo import ZoneInfo

justica_bp = Blueprint('justica', __name__, url_prefix='/justica-e-disciplina')

@justica_bp.route('/')
@login_required
def index():
    try:
        active_school = g.get('active_school')
        
        # CORREÇÃO: Passamos o ID da escola explicitamente para o Service
        school_id = active_school.id if active_school else None
        
        # Busca processos usando o ID da escola garantido
        processos = JusticaService.get_processos_para_usuario(current_user, school_id_override=school_id)
        
        em = [p for p in processos if p.status != 'Finalizado']
        fin = [p for p in processos if p.status == 'Finalizado']
        
        regras = []
        turmas = []
        permite = False
        
        if active_school:
            permite = active_school.npccal_type in ['cspm', 'cbfpm']
            regras = db.session.scalars(select(DisciplineRule).where(DisciplineRule.npccal_type == active_school.npccal_type).order_by(DisciplineRule.codigo)).all()
            turmas = db.session.scalars(select(Turma).where(Turma.school_id == active_school.id).order_by(Turma.nome)).all()

        atributos = [(1, 'Expressão'), (2, 'Planejamento'), (3, 'Perseverança'), (4, 'Apresentação'), (5, 'Lealdade'), (6, 'Tato'), (7, 'Equilíbrio'), (8, 'Disciplina'), (9, 'Responsabilidade'), (10, 'Maturidade'), (11, 'Assiduidade'), (12, 'Pontualidade'), (13, 'Dicção'), (14, 'Liderança'), (15, 'Relacionamento'), (16, 'Ética'), (17, 'Produtividade'), (18, 'Eficiência')]

        return render_template('justica/index.html', em_andamento=em, finalizados=fin, fatos_predefinidos=regras, turmas=turmas, permite_pontuacao=permite, atributos_fada=atributos, hoje=datetime.today().strftime('%Y-%m-%d'))
    except Exception as e:
        traceback.print_exc()
        flash(f"Erro ao carregar painel: {e}", 'danger')
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
        dt = datetime.strptime(dt_str, '%Y-%m-%d').date() if dt_str else datetime.now().date()
        desc = request.form.get('descricao') or request.form.get('fato_descricao')
        
        count = 0
        if tipo == 'infracao':
            regra_id = request.form.get('regra_id')
            pts = float(request.form.get('fato_pontos') or 0.0)
            cod = None
            if regra_id:
                r = db.session.get(DisciplineRule, regra_id)
                if r: pts, cod = r.pontos, r.codigo
            obs = request.form.get('observacao', '')
            for aid in ids:
                JusticaService.criar_processo(desc, obs, int(aid), current_user.id, pts, cod, dt)
                count += 1
            flash(f'{count} infrações registradas.', 'success')
        elif tipo == 'elogio':
            a1, a2 = request.form.get('atributo_1'), request.form.get('atributo_2')
            pts = 0.5 if (a1 or a2) and school.npccal_type in ['cbfpm', 'cspm'] else 0.0
            for aid in ids:
                db.session.add(Elogio(aluno_id=int(aid), registrado_por_id=current_user.id, data_elogio=dt, descricao=desc, pontos=pts, atributo_1=int(a1) if a1 else None, atributo_2=int(a2) if a2 else None))
                count += 1
            db.session.commit()
            flash(f'{count} elogios registrados.', 'success')
        else:
            obs = request.form.get('observacao', '')
            for aid in ids:
                JusticaService.criar_processo(desc, obs, int(aid), current_user.id, 0.0, None, dt)
                count += 1
            flash(f'{count} registros criados.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {e}', 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/novo', methods=['POST'])
@login_required
def novo_processo(): return registrar_em_massa()

@justica_bp.route('/analise')
@login_required
@cal_required 
def analise():
    try:
        dados = JusticaService.get_analise_disciplinar_data()
        return render_template('justica/analise.html', dados=dados)
    except Exception as e:
        flash(f"Erro no dashboard: {e}", "danger")
        return redirect(url_for('justica.index'))

@justica_bp.route('/finalizar/<int:processo_id>', methods=['POST'])
@login_required
def finalizar_processo(processo_id):
    decisao = request.form.get('decisao_final')
    fund = request.form.get('fundamentacao')
    det = request.form.get('detalhes_sancao')
    sus = request.form.get('turnos_sustacao')
    if sus and decisao == 'Sustação da Dispensa': det = f"Sustação: {sus}"
    ok, msg = JusticaService.finalizar_processo(processo_id, decisao, fund, det)
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
    if request.method == 'POST':
        ids = request.form.getlist('processo_ids')
        return Response(render_template('justica/export_bi_template.html', processos=JusticaService.get_processos_por_ids([int(i) for i in ids])), mimetype="application/msword", headers={"Content-disposition": "attachment; filename=export.doc"})
    return render_template('justica/exportar_selecao.html', processos=JusticaService.get_finalized_processos())

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
        if not aluno:
            flash('Aluno não encontrado', 'danger')
            return redirect(url_for('justica.fada_lista_alunos'))

        ciclos = []
        try:
            ciclos = db.session.scalars(select(Ciclo).where(Ciclo.school_id == s.id)).all()
        except: pass

        cid = request.args.get('ciclo_id', type=int)
        if not cid and ciclos: cid = ciclos[-1].id

        previa = JusticaService.calcular_previa_fada(aluno_id, cid) if cid else None
        nome_padrao = current_user.nome_completo or "Avaliador"

        if request.method == 'POST':
            ok, msg, av_id = JusticaService.salvar_fada(request.form, aluno_id, current_user.id, request.form.get('nome_avaliador_custom', nome_padrao))
            if ok:
                flash(msg, 'success')
                return redirect(url_for('justica.fada_gerar_pdf', avaliacao_id=av_id))
            else: flash(msg, 'danger')

        return render_template('justica/fada_formulario.html', aluno=aluno, ciclos=ciclos, ciclo_atual=cid, dados_previa=previa, default_name=nome_padrao)
    except Exception as e:
        traceback.print_exc()
        flash(f"Erro ao abrir avaliação: {str(e)}", 'danger')
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
        return f"Erro PDF: {e}", 500