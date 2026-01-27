from flask import Blueprint, render_template, request, flash, redirect, url_for, g, session, abort
from flask_login import login_required, current_user
from datetime import date, datetime, timedelta
from sqlalchemy import select, or_, and_, func
from sqlalchemy.orm import joinedload
import re
import pytz

from backend.models.database import db
from backend.models.horario import Horario
from backend.models.aluno import Aluno
from backend.models.turma_cargo import TurmaCargo
from backend.models.diario_classe import DiarioClasse
from backend.models.frequencia import FrequenciaAluno
from backend.models.semana import Semana
from backend.models.disciplina import Disciplina
from backend.models.turma import Turma
from backend.models.ciclo import Ciclo

chefe_bp = Blueprint('chefe', __name__, url_prefix='/chefe')

def get_data_hoje_brasil():
    """Retorna a data atual no fuso horário de São Paulo."""
    try:
        tz = pytz.timezone('America/Sao_Paulo')
        return datetime.now(tz).date()
    except Exception:
        return (datetime.utcnow() - timedelta(hours=3)).date()

def get_dia_semana_str(data_obj):
    """Retorna o dia da semana formatado conforme padrão do banco."""
    dias = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
    return dias[data_obj.weekday()]

def get_variacoes_nome_turma(nome_original):
    """Gera variações comuns de nomes de turma para busca flexível."""
    variacoes = {nome_original}
    try:
        match = re.search(r'(\d+)', nome_original)
        if match:
            num_str = match.group(1)
            num_int = int(num_str)
            variacoes.add(f"Turma {num_str}")
            variacoes.add(f"Turma {num_int}")
            variacoes.add(f"{num_str}º Pelotão")
            variacoes.add(f"{num_int}º Pelotão")
            variacoes.add(str(num_int))
    except Exception:
        pass
    return list(variacoes)

def verify_chefe_permission():
    """Retorna o perfil do aluno ou 'admin' para membros da staff."""
    try:
        if not current_user.is_authenticated:
            return None

        active_sid = session.get('active_school_id')
        if current_user.role == 'super_admin' or (hasattr(current_user, 'is_staff_in_school') and current_user.is_staff_in_school(active_sid)):
            return "admin"

        if not current_user.aluno_profile:
            return None
        return current_user.aluno_profile
    except Exception:
        return None

# --- ROTA ATUALIZADA COM LÓGICA DE PERMISSÃO DE EDIÇÃO ---

@chefe_bp.route('/caderno-chamada')
@login_required
def caderno_chamada():
    permissao = verify_chefe_permission()
    if not permissao:
        abort(403)

    pode_editar = False # Padrão: apenas visualização

    if permissao == "admin":
        turma_id = request.args.get('turma_id', type=int)
        if not turma_id:
            flash("Selecione uma turma.", "info")
            return redirect(url_for('main.index'))
        turma = db.session.get(Turma, turma_id)
        pode_editar = True # Admin sempre edita
    else:
        aluno_chefe = Aluno.query.filter_by(user_id=current_user.id).first()
        if not aluno_chefe or not aluno_chefe.turma_id:
            abort(404, description="Vínculo de turma não identificado.")
        turma = db.session.get(Turma, aluno_chefe.turma_id)

        # VERIFICAÇÃO: O aluno logado é o chefe desta turma?
        cargo = TurmaCargo.query.filter_by(turma_id=turma.id, aluno_id=aluno_chefe.id, cargo_nome=TurmaCargo.ROLE_CHEFE).first()
        if cargo:
            pode_editar = True

    if not turma:
        abort(404)

    alunos_turma = Aluno.query.filter_by(turma_id=turma.id)\
        .order_by(Aluno.antiguidade.asc())\
        .all()

    return render_template(
        'chefe_turma/caderno_chamada.html',
        alunos=alunos_turma,
        turma=turma,
        pode_editar=pode_editar,
        is_admin=(permissao == "admin")
    )

# --- FUNÇÕES ORIGINAIS PRESERVADAS ---

@chefe_bp.route('/debug')
@login_required
def debug_screen():
    output = []
    output.append("<h1>Diagnóstico Chefe de Turma (Varredura Semanal Segura)</h1>")

    try:
        permissao = verify_chefe_permission()
        if permissao == "admin":
            aluno = Aluno.query.filter(Aluno.turma_id != None).first()
            output.append("<p style='color:orange'>Modo Admin: Simulando diagnóstico com primeiro aluno encontrado.</p>")
        else:
            aluno = current_user.aluno_profile

        if not aluno or not aluno.turma:
            return "Erro: Aluno sem turma vinculada ou nenhum dado para simular."

        escola_id = aluno.turma.school_id
        data_hoje = get_data_hoje_brasil()
        dia_str = get_dia_semana_str(data_hoje)

        output.append(f"<ul>")
        output.append(f"<li><strong>Aluno:</strong> {aluno.user.nome_completo}</li>")
        output.append(f"<li><strong>Turma ID:</strong> {aluno.turma_id} | <strong>Nome:</strong> {aluno.turma.nome}</li>")
        output.append(f"<li><strong>Escola ID:</strong> {escola_id}</li>")
        output.append(f"<li><strong>Data Base:</strong> {data_hoje} ({dia_str})</li>")
        output.append(f"</ul>")

        semanas = db.session.query(Semana).join(Ciclo).filter(
            Ciclo.school_id == escola_id,
            Semana.data_inicio <= data_hoje,
            Semana.data_fim >= data_hoje
        ).all()

        if not semanas:
            output.append(f"<h3 style='color:red'>ERRO: Nenhuma semana encontrada para a Escola {escola_id} na data de hoje.</h3>")
            output.append("<p>Verifique se existe um Ciclo e uma Semana cadastrados para esta data nesta escola.</p>")
            return "<br>".join(output)

        semana_ids = [s.id for s in semanas]
        nomes_semanas = ", ".join([f"{s.nome} (ID {s.id})" for s in semanas])
        output.append(f"<p><strong>Semanas Ativas Detectadas (Escola {escola_id}):</strong> {nomes_semanas}</p>")

        horarios_raw = db.session.query(Horario)\
            .outerjoin(Horario.disciplina)\
            .outerjoin(Disciplina.turma)\
            .filter(
                Turma.school_id == escola_id,
                Horario.semana_id.in_(semana_ids)
            ).all()

        output.append("<table border='1' cellpadding='5'><tr><th>ID</th><th>Matéria</th><th>Turma ID (Disc)</th><th>Pelotão (Txt)</th><th>Dia no Banco</th><th>Semana ID</th><th>Status</th></tr>")

        variacoes = get_variacoes_nome_turma(aluno.turma.nome)

        if not horarios_raw:
             output.append(f"<tr><td colspan='7'>Nenhum horário encontrado para esta escola nas semanas IDs: {semana_ids}.</td></tr>")

        for h in horarios_raw:
            disc_turma_id = h.disciplina.turma_id if h.disciplina else None
            materia_nome = h.disciplina.materia if h.disciplina else "N/A"

            eh_minha_turma_id = (disc_turma_id == aluno.turma_id)
            eh_meu_nome = (h.pelotao == aluno.turma.nome) or (h.pelotao in variacoes)

            status_txt = "Invisível"
            bg = "#f9f9f9"

            if eh_minha_turma_id:
                status_txt = "<b>Visível (Por ID Turma)</b>"
                bg = "#dff0d8"
            elif eh_meu_nome:
                status_txt = "<b>Visível (Por Nome/Pelotão)</b>"
                bg = "#d9edf7"

            output.append(f"<tr style='background:{bg}'>")
            output.append(f"<td>{h.id}</td>")
            output.append(f"<td>{materia_nome}</td>")
            output.append(f"<td>{disc_turma_id} (Meu: {aluno.turma_id})</td>")
            output.append(f"<td>{h.pelotao}</td>")
            output.append(f"<td>{h.dia_semana}</td>")
            output.append(f"<td>{h.semana_id}</td>")
            output.append(f"<td>{status_txt}</td>")
            output.append("</tr>")
        output.append("</table>")

    except Exception as e:
        import traceback
        output.append(f"<pre>{traceback.format_exc()}</pre>")

    return "<br>".join(output)

@chefe_bp.route('/painel')
@login_required
def painel():
    try:
        aulas_agrupadas = []
        permissao = verify_chefe_permission()

        if not permissao:
            flash("Acesso restrito.", "danger")
            return redirect(url_for('main.index'))

        if permissao == "admin":
            turma_id = request.args.get('turma_id', type=int)
            if not turma_id:
                flash("Administrador, selecione uma turma na lista.", "info")
                return redirect(url_for('main.index'))
            turma_obj = db.session.get(Turma, turma_id)
            aluno = None
        else:
            aluno = permissao
            turma_id = aluno.turma_id
            turma_obj = aluno.turma

        if not turma_obj:
            flash("Turma não encontrada.", "danger")
            return redirect(url_for('main.index'))

        data_str = request.args.get('data')
        data_hoje = get_data_hoje_brasil()
        data_selecionada = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else data_hoje

        semanas_ativas = db.session.query(Semana).join(Ciclo).filter(
            Ciclo.school_id == turma_obj.school_id,
            Semana.data_inicio <= data_selecionada,
            Semana.data_fim >= data_selecionada
        ).all()

        if not semanas_ativas:
            return render_template('chefe/painel.html', aluno=aluno, turma=turma_obj, aulas_agrupadas=[], data_selecionada=data_selecionada, erro_semana=True)

        semana_ids = [s.id for s in semanas_ativas]
        dia_str = get_dia_semana_str(data_selecionada)
        variacoes_nome = get_variacoes_nome_turma(turma_obj.nome)

        query = db.session.query(Horario)\
            .outerjoin(Horario.disciplina)\
            .outerjoin(Disciplina.turma)\
            .options(
                joinedload(Horario.disciplina),
                joinedload(Horario.instrutor)
            ).filter(
                Turma.school_id == turma_obj.school_id,
                Horario.semana_id.in_(semana_ids),
                Horario.dia_semana.ilike(f"{dia_str}%")
            )

        query = query.filter(
            or_(
                Disciplina.turma_id == turma_id,
                Horario.pelotao == turma_obj.nome,
                Horario.pelotao.in_(variacoes_nome)
            )
        )

        horarios = query.order_by(Horario.periodo).all()

        diarios_hoje = db.session.query(DiarioClasse).filter_by(
            data_aula=data_selecionada,
            turma_id=turma_id
        ).all()

        aulas_concluidas_keys = set()
        # CORREÇÃO AQUI: De diaries_hoje para diarios_hoje
        for d in diarios_hoje:
            if d.periodo:
                aulas_concluidas_keys.add(f"{d.disciplina_id}_{d.periodo}")
            else:
                aulas_concluidas_keys.add(f"{d.disciplina_id}_legacy")

        grupos_dict = {}

        if horarios:
            for h in horarios:
                if not h.disciplina:
                    continue

                disc_id = h.disciplina_id

                if disc_id not in grupos_dict:
                    nome_instrutor = "N/A"
                    if h.instrutor:
                        if hasattr(h.instrutor, 'user') and h.instrutor.user:
                            nome_instrutor = h.instrutor.user.nome_de_guerra or h.instrutor.user.nome_completo
                        elif hasattr(h.instrutor, 'nome_guerra'):
                            nome_instrutor = h.instrutor.nome_guerra

                    grupos_dict[disc_id] = {
                        'disciplina': h.disciplina,
                        'nome_instrutor': nome_instrutor,
                        'horarios_reais': [],
                        'periodos_expandidos': [],
                        'status': 'pendente',
                        'primeiro_horario_id': h.id,
                        'total_tempos': 0,
                        'tempos_concluidos': 0
                    }

                duracao = h.duracao if h.duracao and h.duracao > 0 else 1
                grupos_dict[disc_id]['horarios_reais'].append(h)
                grupos_dict[disc_id]['total_tempos'] += duracao

                for i in range(duracao):
                    p = h.periodo + i
                    grupos_dict[disc_id]['periodos_expandidos'].append(p)

                    key = f"{disc_id}_{p}"
                    legacy_key = f"{disc_id}_legacy"

                    if key in aulas_concluidas_keys or legacy_key in aulas_concluidas_keys or h.status == 'concluido':
                        grupos_dict[disc_id]['tempos_concluidos'] += 1

            for g in sorted(grupos_dict.values(), key=lambda x: min(x['periodos_expandidos'])):
                g['periodos'] = sorted(list(set(g['periodos_expandidos'])))
                if g['tempos_concluidos'] >= g['total_tempos'] and g['total_tempos'] > 0:
                    g['status'] = 'concluido'
                aulas_agrupadas.append(g)

        return render_template('chefe/painel.html', aluno=aluno, turma=turma_obj, aulas_agrupadas=aulas_agrupadas, data_selecionada=data_selecionada, erro_semana=False, is_admin=(permissao == "admin"))

    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"Erro no painel: {str(e)}", "danger")
        return redirect(url_for('main.index'))

@chefe_bp.route('/registrar/<int:primeiro_horario_id>', methods=['GET', 'POST'])
@login_required
def registrar_aula(primeiro_horario_id):
    try:
        permissao = verify_chefe_permission()
        if not permissao: return redirect(url_for('main.index'))

        aluno_user = Aluno.query.filter_by(user_id=current_user.id).first()
        is_chefe = False
        horario_base_temp = db.session.get(Horario, primeiro_horario_id)

        if horario_base_temp and aluno_user:
            turma_id_alvo = horario_base_temp.disciplina.turma_id
            cargo = TurmaCargo.query.filter_by(turma_id=turma_id_alvo, aluno_id=aluno_user.id, cargo_nome=TurmaCargo.ROLE_CHEFE).first()
            if cargo:
                is_chefe = True

        if request.method == 'POST' and not (permissao == "admin" or is_chefe):
            flash("Apenas o Chefe de Turma pode registrar presenças.", "danger")
            return redirect(url_for('chefe.caderno_chamada'))

        horario_base_temp = db.session.get(Horario, primeiro_horario_id)
        if not horario_base_temp:
            flash("Horário não encontrado.", "danger")
            return redirect(url_for('chefe.painel'))

        turma_id_alvo = horario_base_temp.disciplina.turma_id
        escola_id_alvo = horario_base_temp.disciplina.turma.school_id

        horario_base = db.session.query(Horario)\
            .outerjoin(Horario.disciplina)\
            .outerjoin(Disciplina.turma)\
            .filter(
                Horario.id == primeiro_horario_id,
                Turma.school_id == escola_id_alvo
            ).first()

        if not horario_base:
            flash("Horário não encontrado.", "danger")
            return redirect(url_for('chefe.painel'))

        data_str = request.args.get('data')
        data_hoje = get_data_hoje_brasil()
        data_aula = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else data_hoje

        variacoes_nome = get_variacoes_nome_turma(horario_base.disciplina.turma.nome)

        horarios_db = db.session.query(Horario)\
            .outerjoin(Horario.disciplina)\
            .outerjoin(Disciplina.turma)\
            .filter(
                Turma.school_id == escola_id_alvo,
                Horario.semana_id == horario_base.semana_id,
                Horario.dia_semana == horario_base.dia_semana,
                Horario.disciplina_id == horario_base.disciplina_id,
                or_(
                    Disciplina.turma_id == turma_id_alvo,
                    Horario.pelotao == horario_base.disciplina.turma.nome,
                    Horario.pelotao.in_(variacoes_nome)
                )
            ).order_by(Horario.periodo).all()

        horarios_expandidos = []
        for h in horarios_db:
            duracao = h.duracao if h.duracao and h.duracao > 0 else 1
            for i in range(duracao):
                p = h.periodo + i
                existe = db.session.query(DiarioClasse).filter_by(
                    data_aula=data_aula,
                    turma_id=turma_id_alvo,
                    disciplina_id=h.disciplina_id,
                    periodo=p
                ).first()

                if not existe:
                    horarios_expandidos.append({'periodo': p, 'horario_pai_id': h.id, 'obj': h})

        horarios_expandidos.sort(key=lambda x: x['periodo'])

        if not horarios_expandidos:
            flash("Todas as aulas desta disciplina já foram registradas para hoje.", "info")
            return redirect(url_for('chefe.painel', data=data_aula, turma_id=turma_id_alvo))

        alunos_turma = db.session.query(Aluno).filter_by(turma_id=turma_id_alvo).order_by(Aluno.num_aluno).all()

        if request.method == 'POST':
            try:
                ids_horarios_pais_atualizados = set()
                count_regs = 0
                for h_virt in horarios_expandidos:
                    periodo_atual = h_virt['periodo']
                    horario_pai = h_virt['obj']

                    novo_diario = DiarioClasse(
                        data_aula=data_aula,
                        turma_id=turma_id_alvo,
                        disciplina_id=horario_pai.disciplina_id,
                        responsavel_id=current_user.id,
                        observacoes=request.form.get('observacoes'),
                        conteudo_ministrado=request.form.get('conteudo'),
                        periodo=periodo_atual
                    )
                    db.session.add(novo_diario)
                    db.session.flush()

                    for aluno in alunos_turma:
                        key = f"presenca_{aluno.id}_{periodo_atual}"
                        presente = request.form.get(key) == 'on'
                        db.session.add(FrequenciaAluno(diario_id=novo_diario.id, aluno_id=aluno.id, presente=presente))

                    if horario_pai.id not in ids_horarios_pais_atualizados:
                        horario_pai.status = 'concluido'
                        db.session.add(horario_pai)
                        ids_horarios_pais_atualizados.add(horario_pai.id)

                    count_regs += 1

                db.session.commit()
                flash(f"Salvo com sucesso! {count_regs} tempos registrados.", "success")
                return redirect(url_for('chefe.painel', data=data_aula, turma_id=turma_id_alvo))
            except Exception as e:
                db.session.rollback()
                flash(f"Erro ao salvar: {str(e)}", "danger")

        nome_instrutor = "N/A"
        if horario_base.instrutor:
             if hasattr(horario_base.instrutor, 'user') and horario_base.instrutor.user:
                 nome_instrutor = horario_base.instrutor.user.nome_de_guerra

        return render_template('chefe/registrar.html', horarios=horarios_expandidos, disciplina=horario_base.disciplina, nome_instrutor=nome_instrutor, alunos=alunos_turma, data_aula=data_aula, turma_id=turma_id_alvo)

    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"Erro: {str(e)}", "danger")
        return redirect(url_for('chefe.painel'))