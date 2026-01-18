# backend/controllers/justica_controller.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, Response
from flask_login import login_required, current_user
from sqlalchemy import select, and_, or_, func, desc
from datetime import datetime
from weasyprint import HTML
import logging

from ..models.database import db
from ..models.processo_disciplina import ProcessoDisciplina, StatusProcesso
from ..models.elogio import Elogio
from ..models.aluno import Aluno
from ..models.user import User 
from ..models.turma import Turma
from ..models.discipline_rule import DisciplineRule
from ..models.fada_avaliacao import FadaAvaliacao
from ..services.justica_service import JusticaService
from ..services.user_service import UserService
from ..services.turma_service import TurmaService
from utils.decorators import admin_or_programmer_required, can_manage_justice_required

justica_bp = Blueprint('justica', __name__, url_prefix='/justica-e-disciplina')
logger = logging.getLogger(__name__)

@justica_bp.route('/')
@login_required
def index():
    school_id = UserService.get_current_school_id()
    if not school_id:
        flash("Nenhuma escola selecionada.", "warning")
        return redirect(url_for('main.dashboard'))

    # Processos em Andamento
    stmt_andamento = select(ProcessoDisciplina).join(Aluno).join(Turma).where(
        Turma.school_id == school_id,
        ProcessoDisciplina.status != StatusProcesso.FINALIZADO,
        ProcessoDisciplina.status != StatusProcesso.ARQUIVADO
    ).order_by(ProcessoDisciplina.data_ocorrencia.desc())
    em_andamento = db.session.scalars(stmt_andamento).all()

    # Processos Finalizados
    stmt_finalizados = select(ProcessoDisciplina).join(Aluno).join(Turma).where(
        Turma.school_id == school_id,
        or_(ProcessoDisciplina.status == StatusProcesso.FINALIZADO, ProcessoDisciplina.status == StatusProcesso.ARQUIVADO)
    ).order_by(ProcessoDisciplina.data_decisao.desc()).limit(50)
    finalizados = db.session.scalars(stmt_finalizados).all()

    # Dados para formulários
    turmas = TurmaService.get_turmas_by_school(school_id)
    fatos_predefinidos = db.session.scalars(select(DisciplineRule).order_by(DisciplineRule.codigo)).all()
    
    agora_hora = datetime.now().strftime('%H:%M')
    hoje = datetime.now().strftime('%Y-%m-%d')

    return render_template('justica/index.html', 
                           em_andamento=em_andamento, 
                           finalizados=finalizados,
                           turmas=turmas,
                           fatos_predefinidos=fatos_predefinidos,
                           agora_hora=agora_hora,
                           hoje=hoje)

@justica_bp.route('/registrar-em-massa', methods=['POST'])
@login_required
@can_manage_justice_required
def registrar_em_massa():
    tipo = request.form.get('tipo_registro')
    alunos_ids = request.form.getlist('alunos_selecionados') or request.form.getlist('alunos_selecionados[]')
    
    data_fato_str = request.form.get('data_fato', datetime.now().strftime('%Y-%m-%d'))
    hora_fato = request.form.get('hora_fato', '12:00')
    descricao = request.form.get('descricao')
    
    try:
        data_completa = datetime.strptime(f"{data_fato_str} {hora_fato}", "%Y-%m-%d %H:%M").astimezone()
    except:
        data_completa = datetime.now().astimezone()

    if not alunos_ids:
        flash("Nenhum aluno selecionado.", "warning")
        return redirect(url_for('justica.index'))

    count = 0
    if tipo == 'infracao':
        regra_id = request.form.get('regra_id')
        observacao = request.form.get('observacao')
        origem_punicao = request.form.get('origem_punicao', 'NPCCAL')
        is_crime_str = request.form.get('is_crime', 'false')
        is_crime = (is_crime_str.lower() == 'true')
        codigo_infracao_manual = request.form.get('codigo_infracao')

        pontos_iniciais = 0.0
        codigo_final = codigo_infracao_manual
        
        if regra_id and origem_punicao == 'NPCCAL':
            regra = db.session.get(DisciplineRule, regra_id)
            if regra: 
                pontos_iniciais = regra.pontos
                codigo_final = regra.codigo

        for aid in alunos_ids:
            try:
                novo_processo = ProcessoDisciplina(
                    aluno_id=int(aid),
                    relator_id=current_user.id,
                    regra_id=regra_id if (regra_id and origem_punicao == 'NPCCAL') else None,
                    codigo_infracao=codigo_final,
                    fato_constatado=descricao,
                    observacao=observacao,
                    data_ocorrencia=data_completa,
                    data_registro=datetime.now().astimezone(),
                    status=StatusProcesso.AGUARDANDO_CIENCIA,
                    origem_punicao=origem_punicao,
                    is_crime=is_crime,
                    pontos=pontos_iniciais
                )
                db.session.add(novo_processo)
                count += 1
            except Exception as e:
                logger.error(f"Erro ao criar processo aluno {aid}: {e}")

    elif tipo == 'elogio':
        for aid in alunos_ids:
            try:
                novo_elogio = Elogio(
                    aluno_id=int(aid),
                    registrado_por_id=current_user.id,
                    data_elogio=data_completa,
                    descricao=descricao,
                    pontos=0.5
                )
                db.session.add(novo_elogio)
                count += 1
            except Exception as e:
                logger.error(f"Erro ao criar elogio aluno {aid}: {e}")

    try:
        db.session.commit()
        flash(f"{count} registros criados com sucesso.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao salvar no banco: {e}", "danger")
        
    return redirect(url_for('justica.index'))

@justica_bp.route('/deletar-processo/<int:pid>', methods=['POST'])
@login_required
@can_manage_justice_required
def deletar_processo(pid):
    """Rota necessária para o template index.html funcionar"""
    processo = db.session.get(ProcessoDisciplina, pid)
    if not processo:
        flash("Processo não encontrado.", "danger")
        return redirect(url_for('justica.index'))
    
    school_id = UserService.get_current_school_id()
    if not processo.aluno or not processo.aluno.turma or processo.aluno.turma.school_id != school_id:
        if not (current_user.is_programador or getattr(current_user, 'role', '') == 'super_admin'):
            flash("Permissão negada.", "danger")
            return redirect(url_for('justica.index'))

    success, message = JusticaService.deletar_processo(pid)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('justica.index'))

# --- FADA / AVALIAÇÃO ATITUDINAL ---

@justica_bp.route('/fada/boletim')
@login_required
def fada_boletim():
    school_id = UserService.get_current_school_id()
    if not school_id: return redirect(url_for('main.dashboard'))
    
    # Filtro opcional por turma
    turma_id = request.args.get('turma_id', type=int)
    
    # Monta Query
    query = select(Aluno).join(Turma).join(User).where(Turma.school_id == school_id)
    if turma_id:
        query = query.where(Turma.id == turma_id)
        
    query = query.order_by(Turma.nome, User.nome_completo)
    
    alunos = db.session.scalars(query).all()
    turmas = TurmaService.get_turmas_by_school(school_id)
    
    lista = []
    for aluno in alunos:
        aat, ndisc, fada = JusticaService.calcular_aat_final(aluno.id)
        lista.append({
            'id': aluno.id,
            'aluno': aluno, # Objeto completo para acessar .user.nome no template
            'turma': aluno.turma.nome,
            'ndisc': ndisc,
            'fada': fada,
            'aat': aat
        })
        
    return render_template('justica/fada_lista_alunos.html', dados=lista, turmas=turmas)

@justica_bp.route('/api/infracoes-pendentes/<int:aluno_id>')
@login_required
def api_infracoes_pendentes(aluno_id):
    aluno = db.session.get(Aluno, aluno_id)
    if not aluno: return jsonify([])
    
    dt_inicio, dt_limite = JusticaService.get_datas_limites(aluno.turma_id)
    
    stmt_proc = select(ProcessoDisciplina).where(
        ProcessoDisciplina.aluno_id == aluno_id,
        ProcessoDisciplina.status == StatusProcesso.FINALIZADO
    )
    processos = db.session.scalars(stmt_proc).all()
    
    stmt_elo = select(Elogio).where(Elogio.aluno_id == aluno_id)
    elogios = db.session.scalars(stmt_elo).all()
    
    resultado = []
    
    for p in processos:
        if JusticaService.verificar_elegibilidade_punicao(p, dt_inicio, dt_limite):
            pontos = 0.0
            desc_texto = ""
            
            if p.is_crime: 
                pontos = 3.0
                desc_texto = "Crime Militar/Comum"
            elif p.origem_punicao == 'RDBM': 
                pontos = 2.0
                desc_texto = f"Transgressão RDBM ({p.codigo_infracao or ''})"
            elif p.pontos:
                pontos = p.pontos
                desc_texto = f"Falta NPCCAL ({p.codigo_infracao or ''})"
                
            if pontos > 0:
                resultado.append({
                    'id': f"inf_{p.id}",
                    'descricao': desc_texto,
                    'data': p.data_ocorrencia.strftime('%d/%m/%Y'),
                    'pontos': pontos,
                    'tipo': 'infracao'
                })

    for e in elogios:
        resultado.append({
            'id': f"elo_{e.id}",
            'descricao': e.descricao or "Elogio registrado",
            'data': e.data_elogio.strftime('%d/%m/%Y'),
            'pontos': 0.50,
            'tipo': 'elogio'
        })
                
    return jsonify(resultado)

@justica_bp.route('/fada/salvar', methods=['POST'])
@login_required
@can_manage_justice_required
def salvar_fada():
    aluno_id = request.form.get('aluno_id')
    notas = request.form.getlist('notas[]')
    observacao = request.form.get('observacao')
    
    if not aluno_id or not notas:
        flash("Dados inválidos.", "danger")
        return redirect(url_for('justica.fada_boletim'))
        
    try:
        soma = sum(float(n) for n in notas)
        media_final = soma / 18.0
        
        nova_fada = FadaAvaliacao(
            aluno_id=int(aluno_id),
            avaliador_id=current_user.id,
            data_avaliacao=datetime.now().astimezone(),
            media_final=media_final,
            observacoes=observacao
        )
        
        db.session.add(nova_fada)
        db.session.commit()
        
        flash(f"Avaliação salva com sucesso. Média: {media_final:.2f}", "success")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao salvar FADA: {e}")
        flash("Erro ao salvar avaliação.", "danger")
        
    return redirect(url_for('justica.fada_boletim'))

# --- UTILITÁRIOS ---

@justica_bp.route('/api/alunos-por-turma/<int:turma_id>')
@login_required
def get_alunos_turma(turma_id):
    alunos = db.session.scalars(select(Aluno).join(User).where(Aluno.turma_id == turma_id).order_by(User.nome_completo)).all()
    data = []
    for a in alunos:
        data.append({
            'id': a.id,
            'nome': a.user.nome_completo,
            'numero': a.numero or '',
            'graduacao': a.user.posto_graduacao or ''
        })
    return jsonify(data)

@justica_bp.route('/api/aluno-details/<int:aluno_id>')
@login_required
def get_aluno_details(aluno_id):
    aluno = db.session.get(Aluno, aluno_id)
    if not aluno: return jsonify({})
    return jsonify({
        'nome_completo': aluno.user.nome_completo,
        'matricula': aluno.user.matricula,
        'posto_graduacao': aluno.user.posto_graduacao or 'Aluno'
    })

@justica_bp.route('/exportar-selecao')
@login_required
def exportar_selecao():
    return render_template('justica/exportar_selecao.html')
    
@justica_bp.route('/teste-modal')
def teste_modal():
    return render_template('justica/teste_modal.html')