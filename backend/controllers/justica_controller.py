# backend/controllers/justica_controller.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import select, or_
from datetime import datetime
import uuid
import hashlib
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

# --- HELPER DE HIERARQUIA ---
def get_rank_value(posto):
    """Retorna valor numérico para hierarquia (Maior valor = Maior patente)"""
    if not posto: return 0
    p = posto.lower().strip()
    
    if 'cel' in p: return 100
    if 'maj' in p: return 80
    if 'cap' in p: return 70
    if '1º ten' in p or '1 ten' in p: return 60
    if '2º ten' in p or '2 ten' in p or 'tenente' in p: return 50
    if 'asp' in p: return 45
    if 'sub' in p: return 40
    if '1º sgt' in p or '1 sgt' in p: return 30
    if '2º sgt' in p or '2 sgt' in p: return 20
    if '3º sgt' in p or '3 sgt' in p: return 10
    if 'cb' in p: return 5
    if 'sd' in p: return 1
    return 0

@justica_bp.route('/')
@login_required
def index():
    school_id = UserService.get_current_school_id()
    if not school_id:
        flash("Nenhuma escola selecionada.", "warning")
        return redirect(url_for('main.dashboard'))

    stmt_andamento = select(ProcessoDisciplina).join(Aluno).join(Turma).where(
        Turma.school_id == school_id,
        ProcessoDisciplina.status != StatusProcesso.FINALIZADO,
        ProcessoDisciplina.status != StatusProcesso.ARQUIVADO
    ).order_by(ProcessoDisciplina.data_ocorrencia.desc())
    em_andamento = db.session.scalars(stmt_andamento).all()

    stmt_finalizados = select(ProcessoDisciplina).join(Aluno).join(Turma).where(
        Turma.school_id == school_id,
        or_(ProcessoDisciplina.status == StatusProcesso.FINALIZADO, ProcessoDisciplina.status == StatusProcesso.ARQUIVADO)
    ).order_by(ProcessoDisciplina.data_decisao.desc()).limit(50)
    finalizados = db.session.scalars(stmt_finalizados).all()

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
    
    turma_id = request.args.get('turma_id', type=int)
    
    # 1. Alunos
    query = select(Aluno).join(Turma).join(User).where(Turma.school_id == school_id)
    if turma_id: query = query.where(Turma.id == turma_id)
    query = query.order_by(Turma.nome, User.nome_completo)
    alunos = db.session.scalars(query).all()
    
    # 2. Turmas
    turmas = TurmaService.get_turmas_by_school(school_id)
    
    # 3. Avaliadores (Staff) - Filtro seguro em Python
    query_staff = select(User).where(User.role != 'aluno').order_by(User.nome_completo)
    all_users = db.session.scalars(query_staff).all()
    
    staff_users = []
    for u in all_users:
        try:
            if hasattr(u, 'schools'):
                if any(str(s.id) == str(school_id) for s in u.schools):
                    staff_users.append(u)
        except: continue
            
    # Garante que o usuário atual (Chefe CAL/Comandante) esteja na lista
    if current_user not in staff_users:
        staff_users.append(current_user)

    lista = []
    for aluno in alunos:
        fada_obj = db.session.scalar(
            select(FadaAvaliacao)
            .where(FadaAvaliacao.aluno_id == aluno.id)
            .order_by(FadaAvaliacao.id.desc())
        )
        aat, ndisc, fada_val = JusticaService.calcular_aat_final(aluno.id)
        lista.append({
            'id': aluno.id,
            'aluno': aluno,
            'turma': aluno.turma.nome,
            'ndisc': ndisc,
            'fada': fada_val,
            'aat': aat,
            'fada_obj': fada_obj
        })
        
    return render_template('justica/fada_lista_alunos.html', 
                           dados=lista, 
                           turmas=turmas, 
                           avaliadores=staff_users)

@justica_bp.route('/fada/salvar', methods=['POST'])
@login_required
@can_manage_justice_required
def salvar_fada():
    aluno_id = request.form.get('aluno_id')
    notas = request.form.getlist('notas[]')
    observacao = request.form.get('observacao')
    
    # Comissão
    presidente_id = request.form.get('presidente_id')
    membro1_id = request.form.get('membro1_id')
    membro2_id = request.form.get('membro2_id')
    
    if not aluno_id or not notas:
        flash("Dados inválidos.", "danger")
        return redirect(url_for('justica.fada_boletim'))
        
    # VALIDAÇÃO HIERARQUIA
    try:
        pres = db.session.get(User, int(presidente_id)) if presidente_id else None
        m1 = db.session.get(User, int(membro1_id)) if membro1_id else None
        m2 = db.session.get(User, int(membro2_id)) if membro2_id else None
        
        if not pres or not m1 or not m2:
            flash("É obrigatório selecionar os 3 membros da comissão.", "danger")
            return redirect(url_for('justica.fada_boletim'))
            
        rank_pres = get_rank_value(pres.posto_graduacao)
        rank_m1 = get_rank_value(m1.posto_graduacao)
        rank_m2 = get_rank_value(m2.posto_graduacao)
        
        # Presidente >= 2º Tenente (Valor 50)
        if rank_pres < 50:
            flash(f"O Presidente ({pres.posto_graduacao}) deve ser no mínimo 2º Tenente.", "danger")
            return redirect(url_for('justica.fada_boletim'))
            
        # Membros >= 2º Sargento (Valor 20)
        if rank_m1 < 20 or rank_m2 < 20:
            flash("Os membros devem ser no mínimo 2º Sargentos.", "danger")
            return redirect(url_for('justica.fada_boletim'))
            
    except Exception as e:
        logger.error(f"Erro validação comissão: {e}")
        flash("Erro ao validar comissão.", "danger")
        return redirect(url_for('justica.fada_boletim'))

    try:
        fada_existente = db.session.scalar(
            select(FadaAvaliacao)
            .where(FadaAvaliacao.aluno_id == int(aluno_id), FadaAvaliacao.status == 'RASCUNHO')
        )

        soma = sum(float(n) for n in notas)
        media_final = soma / 18.0
        
        if fada_existente:
            fada_existente.media_final = media_final
            fada_existente.observacoes = observacao
            fada_existente.data_avaliacao = datetime.now().astimezone()
            fada_existente.presidente_id = int(presidente_id)
            fada_existente.membro1_id = int(membro1_id)
            fada_existente.membro2_id = int(membro2_id)
            # Mantém lancador_id original
        else:
            nova_fada = FadaAvaliacao(
                aluno_id=int(aluno_id),
                lancador_id=current_user.id,
                data_avaliacao=datetime.now().astimezone(),
                media_final=media_final,
                observacoes=observacao,
                status='RASCUNHO',
                presidente_id=int(presidente_id),
                membro1_id=int(membro1_id),
                membro2_id=int(membro2_id)
            )
            db.session.add(nova_fada)
        
        db.session.commit()
        flash(f"Avaliação salva com sucesso. Média: {media_final:.2f}", "success")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao salvar FADA: {e}")
        flash("Erro ao salvar avaliação.", "danger")
        
    return redirect(url_for('justica.fada_boletim'))

@justica_bp.route('/fada/enviar-comissao/<int:fada_id>', methods=['POST'])
@login_required
@can_manage_justice_required
def enviar_fada_comissao(fada_id):
    fada = db.session.get(FadaAvaliacao, fada_id)
    if not fada: return jsonify({'error': 'Erro ID'}), 404
    
    aat, ndisc, _ = JusticaService.calcular_aat_final(fada.aluno_id)
    fada.ndisc_snapshot = ndisc
    fada.aat_snapshot = aat
    fada.status = 'EM_ASSINATURA'
    fada.etapa_atual = 'COMISSAO'
    fada.data_envio = datetime.now().astimezone()
    db.session.commit()
    return jsonify({'success': True, 'message': 'Enviado para assinaturas da comissão.'})

@justica_bp.route('/fada/assinar-membro/<int:fada_id>', methods=['POST'])
@login_required
def assinar_fada_membro(fada_id):
    fada = db.session.get(FadaAvaliacao, fada_id)
    if not fada or fada.etapa_atual != 'COMISSAO':
        return jsonify({'error': 'Documento não disponível.'}), 400
    
    uid = current_user.id
    agora = datetime.now().astimezone()
    ip = request.remote_addr
    novo_hash = hashlib.sha256(f"{uid}-{agora}-{uuid.uuid4()}".encode()).hexdigest()[:16].upper()
    
    assinou = False
    if fada.presidente_id == uid:
        fada.data_ass_pres = agora; fada.hash_pres = novo_hash; fada.ip_pres = ip; assinou = True
    elif fada.membro1_id == uid:
        fada.data_ass_m1 = agora; fada.hash_m1 = novo_hash; fada.ip_m1 = ip; assinou = True
    elif fada.membro2_id == uid:
        fada.data_ass_m2 = agora; fada.hash_m2 = novo_hash; fada.ip_m2 = ip; assinou = True
    
    if not assinou: return jsonify({'error': 'Você não faz parte desta comissão.'}), 403
    
    if fada.hash_pres and fada.hash_m1 and fada.hash_m2:
        fada.etapa_atual = 'ALUNO'
        flash("Assinaturas da comissão completas. Liberado para o aluno.", "success")
    else:
        flash("Sua assinatura foi registrada.", "success")
        
    db.session.commit()
    return redirect(url_for('justica.fada_boletim'))

@justica_bp.route('/fada/assinar-aluno/<int:fada_id>', methods=['POST'])
@login_required
def assinar_fada_aluno(fada_id):
    fada = db.session.get(FadaAvaliacao, fada_id)
    if fada.etapa_atual != 'ALUNO': return jsonify({'error': 'Aguarde comissão.'}), 400
    
    acao = request.form.get('acao')
    if acao == 'assinar':
        fada.status = 'FINALIZADO'; fada.etapa_atual = 'FINALIZADO'
        fada.data_assinatura = datetime.now().astimezone()
        fada.ip_assinatura = request.remote_addr
        fada.hash_integridade = hashlib.sha256(f"FINAL-{fada.id}-{uuid.uuid4()}".encode()).hexdigest()[:20].upper()
        flash("Finalizado com sucesso.", "success")
    elif acao == 'recorrer':
        fada.status = 'RECURSO'; fada.texto_recurso = request.form.get('motivo_recurso')
        flash("Recurso registrado.", "warning")
        
    db.session.commit()
    return redirect(url_for('justica.index'))

# --- UTILITÁRIOS (Rota Restaurada!) ---

@justica_bp.route('/api/alunos-por-turma/<int:turma_id>')
@login_required
def get_alunos_turma(turma_id):
    # Correção: Rota restaurada para listar alunos no select de infração
    stmt = select(Aluno).join(User).where(Aluno.turma_id == turma_id).order_by(User.nome_completo)
    alunos = db.session.scalars(stmt).all()
    data = []
    for a in alunos:
        data.append({
            'id': a.id,
            'nome': a.user.nome_completo,
            # CORREÇÃO: 'num_aluno' em vez de 'numero'
            'numero': getattr(a, 'num_aluno', getattr(a, 'numero', '')), 
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