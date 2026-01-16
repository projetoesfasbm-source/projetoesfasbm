import logging
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, g, session
from flask_login import login_required, current_user
from sqlalchemy import select, desc
from sqlalchemy.orm import joinedload
from datetime import datetime

from ..models.database import db
from ..models.aluno import Aluno
from ..models.user import User
from ..models.turma import Turma
from ..models.processo_disciplina import StatusProcesso, ProcessoDisciplina
from ..models.discipline_rule import DisciplineRule
from ..models.elogio import Elogio
from ..models.fada_avaliacao import FadaAvaliacao
from ..services.justica_service import JusticaService
from utils.decorators import cal_required

logger = logging.getLogger(__name__)
justica_bp = Blueprint('justica', __name__, url_prefix='/justica-e-disciplina')

def _get_current_school_id():
    try:
        if g.get('active_school') and hasattr(g.active_school, 'id'): return int(g.active_school.id)
        if session.get('active_school_id'): return int(session.get('active_school_id'))
        if hasattr(current_user, 'school_id') and current_user.school_id: return int(current_user.school_id)
        if hasattr(current_user, 'schools') and current_user.schools: return int(current_user.schools[0].id)
        if getattr(current_user, 'role', '') == 'aluno' and getattr(current_user, 'aluno_profile', None):
            return int(current_user.aluno_profile.turma.school_id)
    except: pass
    return None

@justica_bp.route('/')
@login_required
def index():
    try:
        school_id = _get_current_school_id()
        processos = JusticaService.get_processos_para_usuario(current_user, school_id_override=school_id)
        
        em_andamento = []
        finalizados = []
        for p in processos:
            s = str(p.status).lower()
            if s == 'finalizado': finalizados.append(p)
            else: em_andamento.append(p)
        
        permite_pontuacao = False
        regras = []
        turmas = []

        if school_id:
            active_school = g.get('active_school')
            if active_school:
                permite_pontuacao, _ = JusticaService.get_pontuacao_config(active_school)
                regras = db.session.scalars(select(DisciplineRule).where(DisciplineRule.npccal_type == active_school.npccal_type).order_by(DisciplineRule.codigo)).all()
            else:
                regras = db.session.scalars(select(DisciplineRule).limit(100)).all()
            turmas = db.session.scalars(select(Turma).where(Turma.school_id == school_id).order_by(Turma.nome)).all()

        atributos = [
            ('expressao', 'Expressão'), ('planejamento', 'Planejamento'), ('perseveranca', 'Perseverança'),
            ('apresentacao', 'Apresentação'), ('lealdade', 'Lealdade'), ('tato', 'Tato'),
            ('equilibrio', 'Equilíbrio'), ('disciplina', 'Disciplina'), ('responsabilidade', 'Responsabilidade'),
            ('maturidade', 'Maturidade'), ('assiduidade', 'Assiduidade'), ('pontualidade', 'Pontualidade'),
            ('diccao', 'Dicção'), ('lideranca', 'Liderança'), ('relacionamento', 'Relacionamento'),
            ('etica', 'Ética'), ('produtividade', 'Produtividade'), ('eficiencia', 'Eficiência')
        ]
        
        agora_hora = datetime.now().strftime('%H:%M')

        return render_template('justica/index.html', 
            em_andamento=em_andamento, finalizados=finalizados, fatos_predefinidos=regras, 
            turmas=turmas, permite_pontuacao=permite_pontuacao, atributos_fada=atributos, 
            hoje=datetime.today().strftime('%Y-%m-%d'), agora_hora=agora_hora)
            
    except Exception:
        logger.exception("Erro index justica")
        flash("Erro ao carregar dados.", "danger")
        return redirect(url_for('main.dashboard'))

@justica_bp.route('/exportar-selecao', methods=['GET'])
@login_required
def exportar_selecao():
    try:
        school_id = _get_current_school_id()
        query = select(ProcessoDisciplina).join(ProcessoDisciplina.aluno).outerjoin(Aluno.turma)
        processos_raw = db.session.scalars(query.order_by(ProcessoDisciplina.data_decisao.desc())).all()
        processos = [p for p in processos_raw if str(p.status).lower() == 'finalizado']
        
        if school_id:
            processos = [p for p in processos if p.aluno.turma.school_id == school_id]
            
        return render_template('justica/exportar_selecao.html', processos=processos)
    except Exception:
        logger.exception("Erro tela exportacao")
        return redirect(url_for('justica.index'))

@justica_bp.route('/imprimir-processos', methods=['POST'])
@login_required
def imprimir_processos():
    try:
        ids = request.form.getlist('processo_ids')
        ids = [int(x) for x in ids if x]
        
        if not ids:
            flash("Nenhum processo selecionado.", "warning")
            return redirect(url_for('justica.exportar_selecao'))
            
        processos = db.session.scalars(
            select(ProcessoDisciplina)
            .where(ProcessoDisciplina.id.in_(ids))
            .options(joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user), joinedload(ProcessoDisciplina.regra))
            .order_by(ProcessoDisciplina.data_ocorrencia.desc())
        ).unique().all()
        
        hoje_extenso = datetime.now().strftime('%d de %B de %Y')
        meses = {'January': 'janeiro', 'February': 'fevereiro', 'March': 'março', 'April': 'abril', 'May': 'maio', 'June': 'junho', 'July': 'julho', 'August': 'agosto', 'September': 'setembro', 'October': 'outubro', 'November': 'novembro', 'December': 'dezembro'}
        for eng, pt in meses.items(): hoje_extenso = hoje_extenso.replace(eng, pt).replace(eng.lower(), pt)

        return render_template('justica/export_bi_template.html', processos=processos, hoje=hoje_extenso)
    except Exception:
        logger.exception("Erro ao gerar impressão")
        flash("Erro técnico na impressão.", "danger")
        return redirect(url_for('justica.index'))

@justica_bp.route('/fada/registrar', methods=['POST'])
@login_required
@cal_required
def registrar_fada():
    try:
        aluno_id = request.form.get('aluno_id')
        if not aluno_id:
            flash("Aluno não selecionado.", "warning")
            return redirect(url_for('justica.index'))
            
        nova_fada = FadaAvaliacao(
            aluno_id=int(aluno_id),
            avaliador_id=current_user.id,
            observacao=request.form.get('observacao'),
            data_avaliacao=datetime.now()
        )
        
        campos = [
            'expressao', 'planejamento', 'perseveranca', 'apresentacao', 'lealdade', 'tato',
            'equilibrio', 'disciplina', 'responsabilidade', 'maturidade', 'assiduidade',
            'pontualidade', 'diccao', 'lideranca', 'relacionamento', 'etica', 'produtividade', 'eficiencia'
        ]
        
        for campo in campos:
            valor = request.form.get(campo)
            if valor:
                setattr(nova_fada, campo, float(valor))
        
        nova_fada.calcular_media()
        db.session.add(nova_fada)
        db.session.commit()
        
        flash(f"Avaliação FADA registrada. Média: {nova_fada.media_final:.2f}", "success")
        return redirect(url_for('justica.index'))
    except Exception:
        db.session.rollback()
        logger.exception("Erro ao registrar FADA")
        flash("Erro ao salvar avaliação.", "danger")
        return redirect(url_for('justica.index'))

@justica_bp.route('/fada/boletim', methods=['GET'])
@login_required
def fada_boletim():
    try:
        school_id = _get_current_school_id()
        if not school_id:
            flash("Nenhuma escola ativa.", "warning")
            return redirect(url_for('justica.index'))

        turma_id = request.args.get('turma_id')
        if turma_id:
            turmas = [db.session.get(Turma, int(turma_id))]
        else:
            turmas = db.session.scalars(select(Turma).where(Turma.school_id == school_id)).all()
        
        dados_boletim = []
        
        for turma in turmas:
            alunos = db.session.scalars(
                select(Aluno).where(Aluno.turma_id == turma.id).join(User).order_by(Aluno.num_aluno)
            ).all()
            
            for aluno in alunos:
                aat, ndisc, fada = JusticaService.calcular_aat_final(aluno.id)
                
                dados_boletim.append({
                    'aluno': aluno,
                    'turma': turma.nome,
                    'ndisc': ndisc,
                    'fada': fada,
                    'aat': aat
                })

        hoje_str = datetime.today().strftime('%d/%m/%Y')

        if request.args.get('print') == 'true':
            return render_template('justica/fada_pdf_template.html', dados=dados_boletim, hoje=hoje_str)

        return render_template('justica/fada_lista_alunos.html', 
                               dados=dados_boletim, 
                               turmas=db.session.scalars(select(Turma).where(Turma.school_id == school_id)).all())
                               
    except Exception as e:
        logger.exception("Erro ao gerar boletim FADA")
        flash(f"Erro ao carregar boletim: {str(e)}", "danger")
        return redirect(url_for('justica.index'))

@justica_bp.route('/registrar-em-massa', methods=['POST'])
@login_required
@cal_required 
def registrar_em_massa():
    try:
        ids = request.form.getlist('alunos_selecionados')
        if not ids and request.form.get('aluno_id'): ids = [request.form.get('aluno_id')]
        if not ids: return redirect(url_for('justica.index'))

        tipo = request.form.get('tipo_registro')
        dt_str = request.form.get('data_fato')
        hr_str = request.form.get('hora_fato')
        desc = request.form.get('descricao')
        obs = request.form.get('observacao', '')

        if dt_str and hr_str: dt_completa = f"{dt_str} {hr_str}"
        else: dt_completa = dt_str

        count = 0
        if tipo == 'infracao':
            regra_id = request.form.get('regra_id')
            pts, cod = 0.0, None
            if regra_id:
                r = db.session.get(DisciplineRule, int(regra_id))
                if r: pts = r.pontos; cod = r.codigo
            for aid in ids:
                ok, _ = JusticaService.criar_processo(desc, obs, int(aid), current_user.id, pts, cod, regra_id, dt_completa)
                if ok: count += 1
            flash(f'{count} infrações registradas.', 'success')
        elif tipo == 'elogio':
            for aid in ids:
                db.session.add(Elogio(aluno_id=int(aid), registrado_por_id=current_user.id, data_elogio=JusticaService._ensure_datetime(dt_str), descricao=desc))
                count += 1
            db.session.commit()
            flash(f'{count} elogios registrados.', 'success')
        return redirect(url_for('justica.index'))
    except: db.session.rollback(); flash("Erro técnico.", "danger"); return redirect(url_for('justica.index'))

@justica_bp.route('/cron/verificar-revelia', methods=['GET'])
def cron_verificar_revelia():
    ok, msgs = JusticaService.verificar_prazos_revelia_automatica()
    return jsonify({'status': 'ok' if ok else 'error', 'processed': msgs}), 200 if ok else 500

@justica_bp.route('/finalizar/<int:pid>', methods=['POST'])
@login_required
@cal_required
def finalizar_processo(pid):
    decisao = request.form.get('decisao_final')
    fundamentacao = request.form.get('fundamentacao')
    detalhes = request.form.get('detalhes_sancao')
    is_crime = request.form.get('is_crime') == 'on'
    tipo_sancao = request.form.get('tipo_sancao')
    origem = request.form.get('origem_punicao', 'NPCCAL')
    dias_str = request.form.get('dias_sancao')
    dias = int(dias_str) if dias_str and dias_str.strip() else None
    
    ok, msg = JusticaService.finalizar_processo(pid, decisao, fundamentacao, detalhes, is_crime=is_crime, tipo_sancao=tipo_sancao, dias_sancao=dias, origem=origem)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/api/alunos-por-turma/<int:turma_id>')
@login_required
def api_alunos_por_turma(turma_id):
    alunos = db.session.scalars(select(Aluno).where(Aluno.turma_id==turma_id).join(User).order_by(Aluno.num_aluno)).all()
    # Modificado para retornar dicionário compatível com Select e Checkbox
    return jsonify([{'id': a.id, 'nome': a.user.nome_completo, 'numero': a.num_aluno or '', 'graduacao': a.user.posto_graduacao or ''} for a in alunos])

@justica_bp.route('/api/aluno-details/<int:aluno_id>')
@login_required
def api_get_aluno_details(aluno_id):
    a = db.session.get(Aluno, aluno_id)
    return jsonify({'nome_completo': a.user.nome_completo, 'posto_graduacao': a.user.posto_graduacao or 'Al', 'matricula': a.user.matricula}) if a else ({}, 404)

@justica_bp.route('/deletar/<int:pid>', methods=['POST'])
@login_required
@cal_required
def deletar_processo(pid):
    JusticaService.deletar_processo(pid); return redirect(url_for('justica.index'))

@justica_bp.route('/ciente/<int:pid>', methods=['POST'])
@login_required
def registrar_ciente(pid):
    JusticaService.registrar_ciente(pid, current_user); return redirect(url_for('justica.index'))

@justica_bp.route('/defesa/<int:pid>', methods=['POST'])
@login_required
def enviar_defesa(pid):
    JusticaService.enviar_defesa(pid, request.form.get('defesa_texto'), current_user); return redirect(url_for('justica.index'))