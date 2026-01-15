import logging
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, Response, g, session
from flask_login import login_required, current_user
from sqlalchemy import select
from datetime import datetime

from ..models.database import db
from ..models.aluno import Aluno
from ..models.user import User
from ..models.turma import Turma
from ..models.processo_disciplina import StatusProcesso, ProcessoDisciplina
from ..models.discipline_rule import DisciplineRule
from ..models.elogio import Elogio
from ..services.justica_service import JusticaService
from utils.decorators import cal_required

logger = logging.getLogger(__name__)
justica_bp = Blueprint('justica', __name__, url_prefix='/justica-e-disciplina')

def _get_current_school_id():
    """Recupera ID da escola de forma robusta com múltiplos fallbacks."""
    try:
        if g.get('active_school') and hasattr(g.active_school, 'id'):
            return int(g.active_school.id)
        sid = session.get('active_school_id')
        if sid: return int(sid)
        if hasattr(current_user, 'school_id') and current_user.school_id:
            return int(current_user.school_id)
        if hasattr(current_user, 'schools') and current_user.schools:
            return int(current_user.schools[0].id)
        if getattr(current_user, 'role', '') == 'aluno':
            if getattr(current_user, 'aluno_profile', None) and current_user.aluno_profile.turma:
                return int(current_user.aluno_profile.turma.school_id)
    except Exception as e:
        logger.error(f"Erro ao recuperar School ID: {e}")
    return None

@justica_bp.route('/')
@login_required
def index():
    try:
        school_id = _get_current_school_id()
        # Busca processos via Service (que já filtra por permissão)
        processos = JusticaService.get_processos_para_usuario(current_user, school_id_override=school_id)
        
        # Separa processos por status usando o .value do Enum para comparação segura
        em_andamento = [p for p in processos if str(p.status) != StatusProcesso.FINALIZADO.value]
        finalizados = [p for p in processos if str(p.status) == StatusProcesso.FINALIZADO.value]
        
        permite_pontuacao = False
        regras = []
        turmas = []

        if school_id:
            active_school = g.get('active_school')
            if active_school:
                permite_pontuacao, _ = JusticaService.get_pontuacao_config(active_school)
                # Busca regras específicas do tipo de escola (CTSP, CBFPM, etc)
                regras = db.session.scalars(
                    select(DisciplineRule)
                    .where(DisciplineRule.npccal_type == active_school.npccal_type)
                    .order_by(DisciplineRule.codigo)
                ).all()
            else:
                regras = db.session.scalars(select(DisciplineRule).limit(100)).all()
            
            turmas = db.session.scalars(
                select(Turma).where(Turma.school_id == school_id).order_by(Turma.nome)
            ).all()

        atributos = [(i, n) for i, n in enumerate([
            'Expressão', 'Planejamento', 'Perseverança', 'Apresentação', 'Lealdade', 'Tato', 
            'Equilíbrio', 'Disciplina', 'Responsabilidade', 'Maturidade', 'Assiduidade', 
            'Pontualidade', 'Dicção', 'Liderança', 'Relacionamento', 'Ética', 'Produtividade', 'Eficiência'
        ], 1)]

        return render_template('justica/index.html', 
            em_andamento=em_andamento, 
            finalizados=finalizados, 
            fatos_predefinidos=regras, 
            turmas=turmas, 
            permite_pontuacao=permite_pontuacao, 
            atributos_fada=atributos, 
            hoje=datetime.today().strftime('%Y-%m-%d'))
            
    except Exception as e:
        logger.exception("Erro crítico no index de justiça")
        # Alteração para ver o erro na tela:
        import traceback
        erro_detalhado = f"{str(e)} | {traceback.format_exc()[-150:]}"
        flash(f"ERRO TÉCNICO REAL: {erro_detalhado}", "danger") 
        return redirect(url_for('main.dashboard'))

@justica_bp.route('/registrar-em-massa', methods=['POST'])
@login_required
@cal_required 
def registrar_em_massa():
    try:
        # Recupera IDs dos alunos (checkboxes)
        ids = request.form.getlist('alunos_selecionados')
        if not ids and request.form.get('aluno_id'):
            ids = [request.form.get('aluno_id')]
            
        if not ids:
            flash('Selecione pelo menos um aluno para realizar o registro.', 'warning')
            return redirect(url_for('justica.index'))

        tipo = request.form.get('tipo_registro')
        dt_str = request.form.get('data_fato')
        desc = request.form.get('descricao')
        obs = request.form.get('observacao', '')

        count = 0
        if tipo == 'infracao':
            regra_id = request.form.get('regra_id')
            pts, cod = 0.0, None
            if regra_id:
                r = db.session.get(DisciplineRule, int(regra_id))
                if r: 
                    pts = r.pontos
                    cod = r.codigo
            
            for aid in ids:
                ok, _ = JusticaService.criar_processo(desc, obs, int(aid), current_user.id, pts, cod, regra_id, dt_str)
                if ok: count += 1
            flash(f'{count} registros de infração realizados com sucesso.', 'success')
        
        elif tipo == 'elogio':
            for aid in ids:
                # O Service trata a conversão da data
                dt = JusticaService._ensure_datetime(dt_str)
                novo_elogio = Elogio(
                    aluno_id=int(aid), 
                    registrado_por_id=current_user.id, 
                    data_elogio=dt, 
                    descricao=desc
                )
                db.session.add(novo_elogio)
                count += 1
            db.session.commit()
            flash(f'{count} elogios registrados com sucesso.', 'success')
            
        return redirect(url_for('justica.index'))
    except Exception as e:
        db.session.rollback()
        logger.exception("Erro ao registrar em massa")
        flash(f"Erro técnico ao salvar: {e}", "danger")
        return redirect(url_for('justica.index'))

@justica_bp.route('/api/alunos-por-turma/<int:turma_id>')
@login_required
def api_alunos_por_turma(turma_id):
    """Retorna lista de alunos para preencher os checkboxes via AJAX."""
    try:
        alunos = db.session.scalars(
            select(Aluno)
            .where(Aluno.turma_id == turma_id)
            .join(User)
            .order_by(Aluno.num_aluno)
        ).all()
        return jsonify([{'id': a.id, 'nome': a.user.nome_completo, 'numero': a.num_aluno} for a in alunos])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@justica_bp.route('/api/aluno-details/<int:aluno_id>')
@login_required
def api_get_aluno_details(aluno_id):
    """Retorna detalhes para o Gerador de Termo Inteligente."""
    try:
        aluno = db.session.get(Aluno, aluno_id)
        if not aluno: return jsonify({'error': 'Aluno não encontrado'}), 404
        return jsonify({
            'nome_completo': aluno.user.nome_completo,
            'posto_graduacao': aluno.user.posto_graduacao or 'Al',
            'matricula': aluno.user.matricula or 'S/M'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@justica_bp.route('/finalizar/<int:pid>', methods=['POST'])
@login_required
@cal_required
def finalizar_processo(pid):
    """Rota para o CAl/Admin decidir o desfecho do processo."""
    decisao = request.form.get('decisao_final')
    fundamentacao = request.form.get('fundamentacao')
    detalhes = request.form.get('detalhes_sancao')
    
    ok, msg = JusticaService.finalizar_processo(pid, decisao, fundamentacao, detalhes)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/deletar/<int:pid>', methods=['POST'])
@login_required
@cal_required
def deletar_processo(pid):
    """Exclui um registro de infração/fato observado."""
    ok, msg = JusticaService.deletar_processo(pid)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/ciente/<int:pid>', methods=['POST'])
@login_required
def registrar_ciente(pid):
    """Rota usada pelo Aluno para assinar a ciência do processo."""
    ok, msg = JusticaService.registrar_ciente(pid, current_user)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/defesa/<int:pid>', methods=['POST'])
@login_required
def enviar_defesa(pid):
    """Rota usada pelo Aluno para enviar sua justificativa escrita."""
    texto = request.form.get('defesa_texto')
    if not texto:
        flash("O texto da defesa não pode estar vazio.", "warning")
        return redirect(url_for('justica.index'))
        
    ok, msg = JusticaService.enviar_defesa(pid, texto, current_user)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('justica.index'))