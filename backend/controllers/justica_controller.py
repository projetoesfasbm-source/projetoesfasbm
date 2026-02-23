# backend/controllers/justica_controller.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, g
from flask_login import login_required, current_user
from sqlalchemy import select, or_
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta
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
from ..services.email_service import EmailService
from ..services.notification_service import NotificationService

from utils.decorators import admin_or_programmer_required, can_manage_justice_required

justica_bp = Blueprint('justica', __name__, url_prefix='/justica-e-disciplina')
logger = logging.getLogger(__name__)

# --- FUNÇÃO DE CONVERSÃO ALGARISMO ROMANO ---
def sort_roman(rule):
    s = str(rule.codigo).upper().strip()
    if s.isdigit(): return int(s)
    rom_val = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    int_val = 0
    for i in range(len(s)):
        if s[i] not in rom_val: return 9999
        if i > 0 and rom_val.get(s[i], 0) > rom_val.get(s[i - 1], 0):
            int_val += rom_val.get(s[i], 0) - 2 * rom_val.get(s[i - 1], 0)
        else:
            int_val += rom_val.get(s[i], 0)
    return int_val

@justica_bp.route('/')
@login_required
def index():
    school_id = UserService.get_current_school_id()
    
    # --- FILTRO DE REGRAS E ORDENAÇÃO ROMANA ---
    tipo_npccal = 'ctsp' 
    if g.active_school and hasattr(g.active_school, 'npccal_type') and g.active_school.npccal_type:
        tipo_npccal = g.active_school.npccal_type.lower()
    
    fatos_predefinidos = db.session.scalars(
        select(DisciplineRule).where(DisciplineRule.npccal_type == tipo_npccal)
    ).all()
    # Ordena inteligentemente respeitando valor romano (I, II, III, IV, IX, X...)
    fatos_predefinidos.sort(key=sort_roman)
    
    if current_user.role == 'aluno':
        if not current_user.aluno_profile or not current_user.aluno_profile.turma:
            flash("Perfil incompleto.", "danger")
            return redirect(url_for('main.dashboard'))
        
        school_id = current_user.aluno_profile.turma.school_id
        g.active_school = current_user.aluno_profile.turma.school
        aluno_id = current_user.aluno_profile.id

        stmt_andamento = select(ProcessoDisciplina).options(
            joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user),
            joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.turma)
        ).where(
            ProcessoDisciplina.aluno_id == aluno_id,
            ProcessoDisciplina.status != StatusProcesso.FINALIZADO.value,
            ProcessoDisciplina.status != StatusProcesso.ARQUIVADO.value
        ).order_by(ProcessoDisciplina.data_ocorrencia.desc())
        
        stmt_finalizados = select(ProcessoDisciplina).options(
            joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user),
            joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.turma)
        ).where(
            ProcessoDisciplina.aluno_id == aluno_id,
            or_(ProcessoDisciplina.status == StatusProcesso.FINALIZADO.value, ProcessoDisciplina.status == StatusProcesso.ARQUIVADO.value)
        ).order_by(ProcessoDisciplina.data_decisao.desc()).limit(50)
    else:
        if not school_id:
            flash("Nenhuma escola selecionada.", "warning")
            return redirect(url_for('main.dashboard'))

        stmt_andamento = select(ProcessoDisciplina).join(Aluno).join(Turma).options(
            joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user),
            joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.turma)
        ).where(
            Turma.school_id == school_id,
            ProcessoDisciplina.status != StatusProcesso.FINALIZADO.value,
            ProcessoDisciplina.status != StatusProcesso.ARQUIVADO.value
        ).order_by(ProcessoDisciplina.data_ocorrencia.desc())

        stmt_finalizados = select(ProcessoDisciplina).join(Aluno).join(Turma).options(
            joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user),
            joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.turma)
        ).where(
            Turma.school_id == school_id,
            or_(ProcessoDisciplina.status == StatusProcesso.FINALIZADO.value, ProcessoDisciplina.status == StatusProcesso.ARQUIVADO.value)
        ).order_by(ProcessoDisciplina.data_decisao.desc()).limit(50)

    # 1. Pega os processos em andamento do BD
    em_andamento = db.session.scalars(stmt_andamento).unique().all()
    
    # 2. Roda a Avaliação Preguiçosa (Lazy Evaluation) para estourar prazos vencidos
    houve_alteracao = JusticaService.verificar_e_atualizar_prazos(em_andamento)
    
    # 3. Se algo mudou, consulta o banco de novo
    if houve_alteracao:
         em_andamento = db.session.scalars(stmt_andamento).unique().all()

    finalizados = db.session.scalars(stmt_finalizados).unique().all()
    
    turmas = TurmaService.get_turmas_by_school(school_id) if school_id else []
    
    agora_hora = datetime.now().strftime('%H:%M')
    hoje = datetime.now().strftime('%Y-%m-%d')
    agora_dt = datetime.now().astimezone()

    return render_template('justica/index.html', 
                           em_andamento=em_andamento, 
                           finalizados=finalizados, 
                           turmas=turmas, 
                           fatos_predefinidos=fatos_predefinidos, 
                           agora_hora=agora_hora, 
                           hoje=hoje,
                           agora=agora_dt)

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
    processos_criados = []

    if tipo == 'infracao':
        regra_id = request.form.get('regra_id')
        observacao = request.form.get('observacao')
        origem_punicao = request.form.get('origem_punicao', 'NPCCAL')
        is_crime = (request.form.get('is_crime', 'false').lower() == 'true')
        codigo_infracao_manual = request.form.get('codigo_infracao')

        pontos_iniciais = 0.0
        codigo_final = codigo_infracao_manual
        
        if regra_id and origem_punicao == 'NPCCAL':
            regra = db.session.get(DisciplineRule, int(regra_id))
            if regra: 
                pontos_iniciais = regra.pontos
                codigo_final = regra.codigo

        for aid in alunos_ids:
            try:
                # GARANTIA SÊNIOR: Forçamos o status como string bruta para o MySQL não se perder
                novo_processo = ProcessoDisciplina(
                    aluno_id=int(aid),
                    relator_id=current_user.id,
                    regra_id=int(regra_id) if (regra_id and origem_punicao == 'NPCCAL') else None,
                    codigo_infracao=codigo_final,
                    fato_constatado=descricao,
                    observacao=observacao,
                    data_ocorrencia=data_completa,
                    data_registro=datetime.now().astimezone(),
                    status=StatusProcesso.AGUARDANDO_CIENCIA.value,
                    origem_punicao=origem_punicao,
                    is_crime=is_crime,
                    pontos=pontos_iniciais
                )
                db.session.add(novo_processo)
                db.session.flush() 
                processos_criados.append(novo_processo)
                count += 1
            except Exception as e:
                logger.error(f"Erro ao criar processo aluno {aid}: {e}")

    # ... (Parte do elogio segue igual) ...
    elif tipo == 'elogio':
        for aid in alunos_ids:
            try:
                novo_elogio = Elogio(aluno_id=int(aid), registrado_por_id=current_user.id, 
                                     data_elogio=data_completa, descricao=descricao, pontos=0.5)
                db.session.add(novo_elogio)
                count += 1
            except Exception as e: 
                logger.error(f"Erro no elogio: {e}")

    db.session.commit()
    flash(f"{count} registros criados.", "success")
    return redirect(url_for('justica.index'))

@justica_bp.route('/dar-ciente/<int:processo_id>', methods=['POST'])
@login_required
def dar_ciente(processo_id):
    processo = db.session.get(ProcessoDisciplina, processo_id)
    if not processo:
        flash("Processo não encontrado.", "error")
        return redirect(url_for('justica.index'))

    is_aluno_dono = (current_user.role == 'aluno' and current_user.aluno_profile and current_user.aluno_profile.id == processo.aluno_id)
    can_manage = (current_user.role != 'aluno')

    if not (is_aluno_dono or can_manage):
        flash("Permissão negada.", "error")
        return redirect(url_for('justica.index'))

    if processo.status == StatusProcesso.AGUARDANDO_CIENCIA.value:
        processo.data_ciencia = datetime.now().astimezone()
        processo.status = StatusProcesso.ALUNO_NOTIFICADO.value
        processo.ciente_aluno = True
        flash("Ciência do processo registrada. Você pode enviar sua defesa.", "success")
    
    elif processo.status == StatusProcesso.DECISAO_EMITIDA.value:
        processo.data_notificacao_decisao = datetime.now().astimezone()
        flash("Ciência da decisão registrada. Prazo de 48h para recurso iniciado.", "info")
    else:
        flash("Este processo já passou da fase de ciência.", "warning")

    db.session.commit()
    return redirect(url_for('justica.index'))

@justica_bp.route('/enviar-defesa/<int:processo_id>', methods=['POST'])
@login_required
def enviar_defesa(processo_id):
    processo = db.session.get(ProcessoDisciplina, processo_id)
    if not processo:
        flash("Processo não encontrado.", "error")
        return redirect(url_for('justica.index'))

    is_aluno_dono = (current_user.role == 'aluno' and current_user.aluno_profile and current_user.aluno_profile.id == processo.aluno_id)
    
    if not is_aluno_dono:
        flash("Permissão negada. Apenas o aluno autuado pode enviar a defesa.", "error")
        return redirect(url_for('justica.index'))
        
    if processo.status != StatusProcesso.ALUNO_NOTIFICADO.value:
        flash("O processo não está aguardando defesa.", "warning")
        return redirect(url_for('justica.index'))
    
    texto_defesa = request.form.get('defesa')
    if not texto_defesa or not texto_defesa.strip():
        flash("A justificativa não pode estar vazia.", "warning")
        return redirect(url_for('justica.index'))

    processo.defesa = texto_defesa
    processo.data_defesa = datetime.now().astimezone()
    processo.status = StatusProcesso.DEFESA_ENVIADA.value

    try:
        db.session.commit()
        flash("Justificativa/Defesa enviada com sucesso.", "success")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao enviar defesa: {e}")
        flash(f"Erro ao salvar defesa: {str(e)}", "danger")

    return redirect(url_for('justica.index'))

@justica_bp.route('/enviar-recurso/<int:pid>', methods=['POST'])
@login_required
def enviar_recurso(pid):
    processo = db.session.get(ProcessoDisciplina, pid)
    
    is_aluno_dono = (current_user.role == 'aluno' and current_user.aluno_profile and current_user.aluno_profile.id == processo.aluno_id)
    if not is_aluno_dono:
        flash("Apenas o aluno pode interpor recurso.", "error"); return redirect(url_for('justica.index'))

    if processo.status != StatusProcesso.DECISAO_EMITIDA.value:
        flash("Status inválido para recurso.", "error"); return redirect(url_for('justica.index'))
    
    if not processo.data_notificacao_decisao:
        flash("Você precisa dar ciência da decisão antes.", "warning"); return redirect(url_for('justica.index'))

    agora = datetime.now().astimezone()
    if processo.data_notificacao_decisao.tzinfo:
        horas_passadas = (agora - processo.data_notificacao_decisao).total_seconds() / 3600
        if horas_passadas > 48:
            flash("Prazo de 48h para recurso expirado.", "error"); return redirect(url_for('justica.index'))

    texto = request.form.get('texto_recurso')
    if not texto:
        flash("Escreva os argumentos do recurso.", "warning"); return redirect(url_for('justica.index'))

    processo.texto_recurso = texto
    processo.data_recurso = agora
    processo.status = StatusProcesso.EM_RECURSO.value

    db.session.commit()
    flash("Recurso enviado ao Comandante.", "success")
    return redirect(url_for('justica.index'))

@justica_bp.route('/finalizar-processo/<int:pid>', methods=['POST'])
@login_required
@can_manage_justice_required
def finalizar_processo(pid):
    """
    Chefe CAL analisa e emite DECISÃO.
    """
    processo = db.session.get(ProcessoDisciplina, pid)
    if not processo:
        flash("Processo não encontrado.", "error"); return redirect(url_for('justica.index'))
        
    if processo.status not in [StatusProcesso.DEFESA_ENVIADA.value, StatusProcesso.EM_ANALISE.value]:
        flash("O processo ainda não está pronto para julgamento.", "warning")
        return redirect(url_for('justica.index'))

    decisao = request.form.get('decisao') 
    fundamentacao_texto = request.form.get('observacao_decisao')
    turnos_sustacao = request.form.get('turnos_sustacao')
    
    try:
        pontos_finais = float(request.form.get('pontos_finais', 0.0))
    except ValueError:
        pontos_finais = 0.0

    if not decisao:
        flash("Selecione uma decisão válida.", "warning"); return redirect(url_for('justica.index'))

    processo.decisao_final = decisao
    processo.data_decisao = datetime.now().astimezone()
    processo.relator_id = current_user.id 
    
    if processo.is_revelia:
        fundamentacao_texto = f"[JULGAMENTO À REVELIA]: {fundamentacao_texto}"
        
    processo.fundamentacao = fundamentacao_texto
    processo.observacao_decisao = fundamentacao_texto

    tipo_npccal = 'ctsp'
    if g.active_school and hasattr(g.active_school, 'npccal_type') and g.active_school.npccal_type:
        tipo_npccal = g.active_school.npccal_type.lower()

    if tipo_npccal == 'cbfpm':
        processo.status = StatusProcesso.DECISAO_EMITIDA.value
        msg_sucesso = "Decisão registrada. O aluno tem 48h para interpor recurso após dar ciência."
    else:
        processo.status = StatusProcesso.FINALIZADO.value
        msg_sucesso = "Decisão confirmada e processo finalizado."

    if decisao in ['Advertência', 'Repreensão']:
        processo.tipo_sancao = decisao
        processo.dias_sancao = 0 
        processo.detalhes_sancao = None
        if pontos_finais > 0:
             processo.pontos = pontos_finais
    
    elif decisao == 'Sustação da Dispensa':
        processo.tipo_sancao = "Sustação da Dispensa"
        processo.detalhes_sancao = turnos_sustacao if turnos_sustacao else "Quantidade não informada"
        processo.dias_sancao = 0
        if pontos_finais > 0:
            processo.pontos = pontos_finais
        
    elif decisao == 'Justificado':
        processo.tipo_sancao = None
        processo.dias_sancao = 0
        processo.detalhes_sancao = None
        processo.pontos = 0.0 

    try:
        db.session.commit()
        aluno = db.session.get(Aluno, processo.aluno_id)
        if aluno and aluno.user:
            link = url_for('justica.index', _external=True)
            NotificationService.create_notification(
                user_id=aluno.user.id,
                message=f"Decisão emitida no processo {processo.id}. Acesse para ciência/recurso.",
                url=link
            )
        flash(msg_sucesso, "success")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao finalizar processo {pid}: {e}")
        flash(f"Erro ao salvar: {str(e)}", "danger")
        
    return redirect(url_for('justica.index'))

@justica_bp.route('/julgar-recurso/<int:pid>', methods=['POST'])
@login_required
def julgar_recurso(pid):
    school_id = UserService.get_current_school_id()
    is_comandante = current_user.is_admin_escola_in_school(school_id)
    
    if not (current_user.is_programador or is_comandante):
        flash("Apenas o Comandante (Admin Escola) pode julgar recursos.", "error")
        return redirect(url_for('justica.index'))

    processo = db.session.get(ProcessoDisciplina, pid)
    decisao = request.form.get('decisao_recurso')
    parecer = request.form.get('fundamentacao_recurso')

    processo.decisao_recurso = decisao
    processo.fundamentacao_recurso = parecer
    processo.autoridade_recurso_id = current_user.id
    processo.data_julgamento_recurso = datetime.now().astimezone()
    
    if decisao == 'DEFERIDO':
        processo.tipo_sancao = "ANULADO (Recurso Deferido)"
        processo.pontos = 0.0
        processo.observacao_decisao += f" | Recurso DEFERIDO pelo Comandante em {datetime.now().strftime('%d/%m')}. Punição anulada."
    else:
        processo.observacao_decisao += f" | Recurso INDEFERIDO pelo Comandante em {datetime.now().strftime('%d/%m')}. Decisão mantida."

    processo.status = StatusProcesso.FINALIZADO.value

    db.session.commit()
    flash("Recurso julgado. Processo finalizado.", "success")
    return redirect(url_for('justica.index'))

@justica_bp.route('/arquivar-processo/<int:pid>', methods=['POST'])
@login_required
@can_manage_justice_required
def arquivar_processo(pid):
    processo = db.session.get(ProcessoDisciplina, pid)
    if not processo:
        flash("Processo não encontrado.", "error"); return redirect(url_for('justica.index'))
    
    processo.status = StatusProcesso.ARQUIVADO.value
    db.session.commit()
    flash("Processo arquivado.", "info")
    return redirect(url_for('justica.index'))

@justica_bp.route('/deletar-processo/<int:pid>', methods=['POST'])
@login_required
@can_manage_justice_required
def deletar_processo(pid):
    processo = db.session.get(ProcessoDisciplina, pid)
    if not processo:
        flash("Processo não encontrado.", "danger"); return redirect(url_for('justica.index'))
    
    school_id = UserService.get_current_school_id()
    if processo.aluno and processo.aluno.turma and processo.aluno.turma.school_id != school_id:
         if not (current_user.is_programador or current_user.is_admin_escola_in_school(school_id)):
             flash("Este processo pertence a outra escola.", "danger")
             return redirect(url_for('justica.index'))

    success, message = JusticaService.deletar_processo(pid)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('justica.index'))

# --- ROTAS FADA ---
@justica_bp.route('/fada/boletim')
@login_required
def fada_boletim():
    school_id = UserService.get_current_school_id()
    if not school_id and current_user.role == 'aluno':
        school_id = current_user.aluno_profile.turma.school_id
        
    if not school_id:
        flash("Nenhuma escola selecionada.", "warning"); return redirect(url_for('main.dashboard'))
    
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
        fada_obj = db.session.scalar(select(FadaAvaliacao).where(FadaAvaliacao.aluno_id == aluno.id).order_by(FadaAvaliacao.id.desc()))
        aat, ndisc, fada_val = JusticaService.calcular_aat_final(aluno.id)
        
        dt_inicio, dt_limite = JusticaService.get_datas_limites(aluno.turma_id)
        punicoes = db.session.scalars(select(ProcessoDisciplina).where(ProcessoDisciplina.aluno_id == aluno.id, ProcessoDisciplina.status == StatusProcesso.FINALIZADO.value)).all()
        punicoes_validas = [p for p in punicoes if JusticaService.verificar_elegibilidade_punicao(p, dt_inicio, dt_limite)]
        
        lista.append({
            'id': aluno.id, 'aluno': aluno, 'turma': aluno.turma.nome,
            'ndisc': ndisc, 'fada': fada_val, 'aat': aat, 'fada_obj': fada_obj, 'punicoes_pendentes': punicoes_validas
        })
        
    return render_template('justica/fada_lista_alunos.html', dados=lista, turmas=turmas, avaliadores=staff_users)

@justica_bp.route('/fada/salvar', methods=['POST'])
@login_required
@can_manage_justice_required
def salvar_fada():
    aluno_id = request.form.get('aluno_id')
    notas = request.form.getlist('notas[]')
    obs = request.form.get('observacao')
    pres_id = request.form.get('presidente_id')
    m1_id = request.form.get('membro1_id')
    m2_id = request.form.get('membro2_id')
    
    if not aluno_id or len(notas) != 18:
        flash("Dados incompletos.", "danger"); return redirect(url_for('justica.fada_boletim'))

    processos_ativos = db.session.scalars(select(ProcessoDisciplina).where(ProcessoDisciplina.aluno_id == int(aluno_id), ProcessoDisciplina.status == StatusProcesso.FINALIZADO.value)).all()
    dt_inicio, dt_limite = JusticaService.get_datas_limites(db.session.get(Aluno, int(aluno_id)).turma_id)
    mapa_vinculos = {}
    
    for p in processos_ativos:
        if JusticaService.verificar_elegibilidade_punicao(p, dt_inicio, dt_limite):
            attr_idx = request.form.get(f'vinculo_infracao_{p.id}')
            if not attr_idx:
                flash(f"ERRO: A punição (ID {p.id}) deve ser vinculada a um atributo.", "danger")
                return redirect(url_for('justica.fada_boletim'))
            mapa_vinculos[str(p.id)] = attr_idx

    limites_calculados, erro_limite = JusticaService.calcular_limites_fada(int(aluno_id), mapa_vinculos)
    if erro_limite:
        flash(f"Erro de Validação: {erro_limite}", "danger"); return redirect(url_for('justica.fada_boletim'))

    notas_float = []
    for i, n_str in enumerate(notas):
        try:
            val = float(n_str)
            teto = limites_calculados[i]
            if val > (teto + 0.01):
                flash(f"ERRO no Atributo {i+1}: Nota {val} excede o limite de {teto:.2f}.", "danger"); return redirect(url_for('justica.fada_boletim'))
            notas_float.append(val)
        except ValueError:
            flash("Nota inválida.", "danger"); return redirect(url_for('justica.fada_boletim'))

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
        db.session.rollback(); flash("Erro ao salvar avaliação.", "danger")
        
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
    processos = db.session.scalars(select(ProcessoDisciplina).where(ProcessoDisciplina.aluno_id==aluno_id, ProcessoDisciplina.status==StatusProcesso.FINALIZADO.value)).all()
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
    stmt = select(ProcessoDisciplina).where(ProcessoDisciplina.status == StatusProcesso.FINALIZADO.value).order_by(ProcessoDisciplina.data_decisao.desc())
    stmt = stmt.options(joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user))
    processos = db.session.scalars(stmt).unique().all()
    return render_template('justica/exportar_selecao.html', processos=processos, datetime=datetime)

@justica_bp.route('/confirmar-publicacao-boletim', methods=['POST'])
@login_required
@can_manage_justice_required
def confirmar_publicacao_boletim():
    ids_selecionados = request.form.getlist('processos_ids')
    num_boletim = request.form.get('numero_boletim')
    
    if not ids_selecionados or not num_boletim:
        flash("Selecione os processos e informe o número do boletim.", "warning")
        return redirect(url_for('justica.exportar_selecao'))
        
    count = 0
    for pid in ids_selecionados:
        proc = db.session.get(ProcessoDisciplina, int(pid))
        if proc:
            msg_pub = f" | Publicado em Boletim nº {num_boletim} em {datetime.now().strftime('%d/%m/%Y')}"
            if proc.observacao_decisao: proc.observacao_decisao += msg_pub
            else: proc.observacao_decisao = msg_pub
            count += 1
            
    db.session.commit()
    flash(f"{count} processos vinculados ao Boletim {num_boletim} com sucesso.", "success")
    return redirect(url_for('justica.exportar_selecao'))