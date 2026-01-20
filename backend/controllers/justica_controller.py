from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, g
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
    
    # LÓGICA DE FILTRO E IDENTIFICAÇÃO DE ESCOLA
    if current_user.role == 'aluno':
        if not current_user.aluno_profile or not current_user.aluno_profile.turma:
            flash("Perfil incompleto.", "danger")
            return redirect(url_for('main.dashboard'))
        
        # Identificação automática da escola do aluno
        school_id = current_user.aluno_profile.turma.school_id
        g.active_school = current_user.aluno_profile.turma.school
        aluno_id = current_user.aluno_profile.id

        stmt_andamento = select(ProcessoDisciplina).where(
            ProcessoDisciplina.aluno_id == aluno_id,
            ProcessoDisciplina.status != StatusProcesso.FINALIZADO,
            ProcessoDisciplina.status != StatusProcesso.ARQUIVADO
        ).order_by(ProcessoDisciplina.data_ocorrencia.desc())
        
        stmt_finalizados = select(ProcessoDisciplina).where(
            ProcessoDisciplina.aluno_id == aluno_id,
            or_(ProcessoDisciplina.status == StatusProcesso.FINALIZADO, ProcessoDisciplina.status == StatusProcesso.ARQUIVADO)
        ).order_by(ProcessoDisciplina.data_decisao.desc()).limit(50)
    else:
        # Administrador/CAL: Exige escola selecionada na sessão administrativa
        if not school_id:
            flash("Nenhuma escola selecionada.", "warning")
            return redirect(url_for('main.dashboard'))

        stmt_andamento = select(ProcessoDisciplina).join(Aluno).join(Turma).where(
            Turma.school_id == school_id,
            ProcessoDisciplina.status != StatusProcesso.FINALIZADO,
            ProcessoDisciplina.status != StatusProcesso.ARQUIVADO
        ).order_by(ProcessoDisciplina.data_ocorrencia.desc())

        stmt_finalizados = select(ProcessoDisciplina).join(Aluno).join(Turma).where(
            Turma.school_id == school_id,
            or_(ProcessoDisciplina.status == StatusProcesso.FINALIZADO, ProcessoDisciplina.status == StatusProcesso.ARQUIVADO)
        ).order_by(ProcessoDisciplina.data_decisao.desc()).limit(50)

    em_andamento = db.session.scalars(stmt_andamento).all()
    finalizados = db.session.scalars(stmt_finalizados).all()
    turmas = TurmaService.get_turmas_by_school(school_id) if school_id else []
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

@justica_bp.route('/dar-ciente/<int:processo_id>', methods=['POST'])
@login_required
def dar_ciente(processo_id):
    """Registra a ciência do aluno no processo."""
    processo = db.session.get(ProcessoDisciplina, processo_id)
    if not processo:
        flash("Processo não encontrado.", "error")
        return redirect(url_for('justica.index'))

    is_aluno_dono = (current_user.role == 'aluno' and current_user.aluno_profile and current_user.aluno_profile.id == processo.aluno_id)
    can_manage = (current_user.role != 'aluno')

    if not (is_aluno_dono or can_manage):
        flash("Permissão negada.", "error")
        return redirect(url_for('justica.index'))

    processo.data_ciencia = datetime.now().astimezone()
    # CORREÇÃO: Status atualizado para ALUNO_NOTIFICADO (Corrigido erro do log)
    processo.status = StatusProcesso.ALUNO_NOTIFICADO 
    
    db.session.commit()
    flash("Ciência registrada com sucesso.", "success")
    return redirect(url_for('justica.index'))

@justica_bp.route('/finalizar-processo/<int:pid>', methods=['POST'])
@login_required
@can_manage_justice_required
def finalizar_processo(pid):
    """Julga e finaliza o processo disciplinar."""
    processo = db.session.get(ProcessoDisciplina, pid)
    if not processo:
        flash("Processo não encontrado.", "error")
        return redirect(url_for('justica.index'))

    decisao = request.form.get('decisao') # 'punir', 'justificar', 'absolver'
    pontos_finais = request.form.get('pontos_finais', type=float)
    observacao_final = request.form.get('observacao_decisao')

    if not decisao:
        flash("Selecione uma decisão.", "warning")
        return redirect(url_for('justica.index'))

    processo.decisao_final = decisao
    processo.observacao_decisao = observacao_final
    processo.data_decisao = datetime.now().astimezone()
    processo.status = StatusProcesso.FINALIZADO

    if decisao == 'punir':
        if pontos_finais is not None:
            processo.pontos = pontos_finais
    elif decisao in ['justificar', 'absolver']:
        processo.pontos = 0.0

    db.session.commit()
    flash("Processo finalizado/julgado com sucesso.", "success")
    return redirect(url_for('justica.index'))

@justica_bp.route('/arquivar-processo/<int:pid>', methods=['POST'])
@login_required
@can_manage_justice_required
def arquivar_processo(pid):
    processo = db.session.get(ProcessoDisciplina, pid)
    if not processo:
        flash("Processo não encontrado.", "error")
        return redirect(url_for('justica.index'))
    
    processo.status = StatusProcesso.ARQUIVADO
    db.session.commit()
    flash("Processo arquivado.", "info")
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

@justica_bp.route('/fada/boletim')
@login_required
def fada_boletim():
    school_id = UserService.get_current_school_id()
    if not school_id and current_user.role == 'aluno':
        school_id = current_user.aluno_profile.turma.school_id
        
    if not school_id:
        flash("Nenhuma escola selecionada.", "warning")
        return redirect(url_for('main.dashboard'))
    
    turma_id = request.args.get('turma_id', type=int)
    
    query = select(Aluno).join(Turma).join(User).where(Turma.school_id == school_id)
    if turma_id: query = query.where(Turma.id == turma_id)
    query = query.order_by(Turma.nome, User.nome_completo)
    alunos = db.session.scalars(query).all()
    
    turmas = TurmaService.get_turmas_by_school(school_id)
    
    query_staff = select(User).where(User.role != 'aluno').order_by(User.nome_completo)
    all_users = db.session.scalars(query_staff).all()
    
    staff_users = []
    for u in all_users:
        try:
            if hasattr(u, 'schools'):
                if any(str(s.id) == str(school_id) for s in u.schools):
                    staff_users.append(u)
        except: continue
            
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
        
        # Pega punições ativas
        dt_inicio, dt_limite = JusticaService.get_datas_limites(aluno.turma_id)
        punicoes = db.session.scalars(select(ProcessoDisciplina).where(
            ProcessoDisciplina.aluno_id == aluno.id,
            ProcessoDisciplina.status == StatusProcesso.FINALIZADO
        )).all()
        punicoes_validas = [p for p in punicoes if JusticaService.verificar_elegibilidade_punicao(p, dt_inicio, dt_limite)]
        
        lista.append({
            'id': aluno.id,
            'aluno': aluno,
            'turma': aluno.turma.nome,
            'ndisc': ndisc,
            'fada': fada_val,
            'aat': aat,
            'fada_obj': fada_obj,
            'punicoes_pendentes': punicoes_validas
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
    notas = request.form.getlist('notas[]') # Lista de 18 notas
    obs = request.form.get('observacao')
    pres_id = request.form.get('presidente_id')
    m1_id = request.form.get('membro1_id')
    m2_id = request.form.get('membro2_id')
    
    if not aluno_id or len(notas) != 18:
        flash("Dados incompletos.", "danger"); return redirect(url_for('justica.fada_boletim'))

    # --- 1. COLETAR VÍNCULOS DE INFRAÇÕES (Obrigatoriedade) ---
    processos_ativos = db.session.scalars(select(ProcessoDisciplina).where(
        ProcessoDisciplina.aluno_id == int(aluno_id),
        ProcessoDisciplina.status == StatusProcesso.FINALIZADO
    )).all()
    
    dt_inicio, dt_limite = JusticaService.get_datas_limites(db.session.get(Aluno, int(aluno_id)).turma_id)
    mapa_vinculos = {}
    
    for p in processos_ativos:
        if JusticaService.verificar_elegibilidade_punicao(p, dt_inicio, dt_limite):
            attr_idx = request.form.get(f'vinculo_infracao_{p.id}')
            if not attr_idx:
                flash(f"ERRO: A punição (ID {p.id}) deve ser vinculada a um atributo.", "danger")
                return redirect(url_for('justica.fada_boletim'))
            mapa_vinculos[str(p.id)] = attr_idx

    # --- 2. CALCULAR LIMITES COM O MAPA FORNECIDO ---
    limites_calculados, erro_limite = JusticaService.calcular_limites_fada(int(aluno_id), mapa_vinculos)
    if erro_limite:
        flash(f"Erro de Validação: {erro_limite}", "danger"); return redirect(url_for('justica.fada_boletim'))

    # --- 3. VALIDAR NOTAS CONTRA LIMITES ---
    notas_float = []
    for i, n_str in enumerate(notas):
        try:
            val = float(n_str)
            teto = limites_calculados[i]
            if val > (teto + 0.01):
                flash(f"ERRO no Atributo {i+1}: Nota {val} excede o limite de {teto:.2f}.", "danger")
                return redirect(url_for('justica.fada_boletim'))
            notas_float.append(val)
        except ValueError:
            flash("Nota inválida.", "danger"); return redirect(url_for('justica.fada_boletim'))

    # --- 4. SALVAR ---
    try:
        fada = db.session.scalar(select(FadaAvaliacao).where(FadaAvaliacao.aluno_id==int(aluno_id), FadaAvaliacao.status=='RASCUNHO'))
        media = sum(notas_float) / 18.0
        
        if fada:
            fada.media_final = media; fada.observacoes = obs; fada.data_avaliacao = datetime.now().astimezone()
            fada.presidente_id = pres_id; fada.membro1_id = m1_id; fada.membro2_id = m2_id
            attrs = ['expressao', 'planejamento', 'perseveranca', 'apresentacao', 'lealdade', 'tato', 'equilibrio', 'disciplina', 'responsabilidade', 'maturidade', 'assiduidade', 'pontualidade', 'diccao', 'lideranca', 'relacionamento', 'etica', 'produtividade', 'eficiencia']
            for idx, attr in enumerate(attrs): setattr(fada, attr, notas_float[idx])
        else:
            nova = FadaAvaliacao(aluno_id=int(aluno_id), lancador_id=current_user.id, media_final=media, observacoes=obs, status='RASCUNHO', presidente_id=pres_id, membro1_id=m1_id, membro2_id=m2_id)
            attrs = ['expressao', 'planejamento', 'perseveranca', 'apresentacao', 'lealdade', 'tato', 'equilibrio', 'disciplina', 'responsabilidade', 'maturidade', 'assiduidade', 'pontualidade', 'diccao', 'lideranca', 'relacionamento', 'etica', 'produtividade', 'eficiencia']
            for idx, attr in enumerate(attrs): setattr(nova, attr, notas_float[idx])
            db.session.add(nova)
            
        db.session.commit()
        flash(f"Avaliação salva com sucesso. Média: {media:.4f}", "success")
    except Exception as e:
        db.session.rollback()
        flash("Erro ao salvar avaliação.", "danger")
        
    return redirect(url_for('justica.fada_boletim'))

@justica_bp.route('/fada/enviar-comissao/<int:fada_id>', methods=['POST'])
@login_required
@can_manage_justice_required
def enviar_fada_comissao(fada_id):
    f = db.session.get(FadaAvaliacao, fada_id)
    if f:
        aat, ndisc, _ = JusticaService.calcular_aat_final(f.aluno_id)
        f.ndisc_snapshot = ndisc; f.aat_snapshot = aat; f.status = 'EM_ASSINATURA'; f.etapa_atual = 'COMISSAO'; f.data_envio = datetime.now().astimezone()
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'Erro'}), 404

@justica_bp.route('/fada/assinar-membro/<int:fada_id>', methods=['POST'])
@login_required
def assinar_fada_membro(fada_id):
    f = db.session.get(FadaAvaliacao, fada_id)
    if not f or f.etapa_atual != 'COMISSAO': return jsonify({'error': 'N/A'}), 400
    
    uid = current_user.id
    h = hashlib.sha256(f"{uid}-{datetime.now()}-{uuid.uuid4()}".encode()).hexdigest()[:16].upper()
    
    if f.presidente_id == uid: f.hash_pres = h; f.data_ass_pres = datetime.now().astimezone()
    elif f.membro1_id == uid: f.hash_m1 = h; f.data_ass_m1 = datetime.now().astimezone()
    elif f.membro2_id == uid: f.hash_m2 = h; f.data_ass_m2 = datetime.now().astimezone()
    else: return jsonify({'error': 'Não autorizado'}), 403
    
    if f.hash_pres and f.hash_m1 and f.hash_m2: f.etapa_atual = 'ALUNO'
    db.session.commit()
    return redirect(url_for('justica.fada_boletim'))

@justica_bp.route('/fada/assinar-aluno/<int:fada_id>', methods=['POST'])
@login_required
def assinar_fada_aluno(fada_id):
    f = db.session.get(FadaAvaliacao, fada_id)
    if f.etapa_atual != 'ALUNO': return jsonify({'error': 'Aguarde'}), 400
    
    if request.form.get('acao') == 'assinar':
        f.status = 'FINALIZADO'; f.etapa_atual = 'FINALIZADO'
        f.data_assinatura = datetime.now().astimezone(); f.ip_assinatura = request.remote_addr
        f.hash_integridade = hashlib.sha256(f"FINAL-{f.id}-{uuid.uuid4()}".encode()).hexdigest()[:20].upper()
        flash("Assinado com sucesso.", "success")
    else:
        f.status = 'RECURSO'; f.texto_recurso = request.form.get('motivo_recurso')
        f.data_assinatura = datetime.now().astimezone()
        flash("Recurso enviado.", "warning")
    
    db.session.commit()
    return redirect(url_for('justica.index'))

@justica_bp.route('/api/infracoes-pendentes/<int:aluno_id>')
@login_required
def api_infracoes_pendentes(aluno_id):
    aluno = db.session.get(Aluno, aluno_id)
    dt_inicio, dt_limite = JusticaService.get_datas_limites(aluno.turma_id)
    processos = db.session.scalars(select(ProcessoDisciplina).where(ProcessoDisciplina.aluno_id==aluno_id, ProcessoDisciplina.status==StatusProcesso.FINALIZADO)).all()
    res = []
    for p in processos:
        if JusticaService.verificar_elegibilidade_punicao(p, dt_inicio, dt_limite):
            res.append({'id': p.id, 'descricao': p.codigo_infracao, 'pontos': p.pontos})
    return jsonify(res)

@justica_bp.route('/api/alunos-por-turma/<int:turma_id>')
@login_required
def get_alunos_turma(turma_id):
    alunos = db.session.scalars(select(Aluno).join(User).where(Aluno.turma_id==turma_id).order_by(User.nome_completo)).all()
    return jsonify([{'id': a.id, 'nome': a.user.nome_completo, 'graduacao': a.user.posto_graduacao or ''} for a in alunos])

@justica_bp.route('/api/aluno-details/<int:aluno_id>')
@login_required
def get_aluno_details(aluno_id):
    a = db.session.get(Aluno, aluno_id)
    return jsonify({'nome_completo': a.user.nome_completo, 'matricula': a.user.matricula, 'posto_graduacao': a.user.posto_graduacao}) if a else jsonify({})

@justica_bp.route('/exportar-selecao')
@login_required
def exportar_selecao():
    return render_template('justica/exportar_selecao.html')