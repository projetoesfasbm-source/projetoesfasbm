# backend/controllers/chefe_turma_controller.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, g
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
from backend.models.user import User  
from backend.services.diario_service import DiarioService

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
    try:
        if not current_user.is_authenticated or not current_user.aluno_profile:
            return None
        return current_user.aluno_profile
    except Exception:
        return None

@chefe_bp.route('/debug')
@login_required
def debug_screen():
    output = []
    output.append("<h1>Diagnóstico Chefe de Turma</h1>")
    
    try:
        aluno = verify_chefe_permission()
        if not aluno or not aluno.turma:
            return "Erro: Aluno sem turma vinculada."
            
        escola_id = aluno.turma.school_id
        
        # Agora o debug aceita a data que queremos investigar!
        data_str = request.args.get('data')
        if data_str:
            data_hoje = datetime.strptime(data_str, '%Y-%m-%d').date()
        else:
            data_hoje = get_data_hoje_brasil()
            
        dia_str = get_dia_semana_str(data_hoje)

        output.append(f"<ul>")
        output.append(f"<li><strong>Aluno:</strong> {aluno.user.nome_completo}</li>")
        output.append(f"<li><strong>Turma ID:</strong> {aluno.turma_id} | <strong>Nome da Turma no Banco (Aluno):</strong> '{aluno.turma.nome}'</li>")
        output.append(f"<li><strong>Data Base:</strong> {data_hoje} | <strong>Dia Buscado (Código):</strong> '{dia_str}'</li>")
        output.append(f"</ul>")
        
        semanas_ativas = db.session.query(Semana).join(Ciclo).filter(
            Ciclo.school_id == escola_id,
            Ciclo.edicao_id == aluno.turma.edicao_id,
            Semana.data_inicio <= data_hoje,
            Semana.data_fim >= data_hoje
        ).all()

        if not semanas_ativas:
            output.append("<p style='color:orange'>Aviso: Nenhuma semana exata encontrada. Testando o Fallback...</p>")
            fallback_semana = db.session.query(Semana).join(Ciclo).filter(
                Ciclo.school_id == escola_id,
                Ciclo.edicao_id == aluno.turma.edicao_id,
                Semana.data_inicio <= data_hoje
            ).order_by(Semana.data_inicio.desc()).first()
            
            if fallback_semana:
                semanas_ativas = [fallback_semana]
            else:
                output.append("<h3 style='color:red'>ERRO FATAL: Nem o fallback encontrou uma semana antes dessa data!</h3>")
                return "<br>".join(output)
        
        semana_ids = [s.id for s in semanas_ativas]
        nomes_semanas = ", ".join([f"{s.nome} (ID {s.id})" for s in semanas_ativas])
        output.append(f"<p><strong>Semanas Detectadas:</strong> {nomes_semanas}</p>")

        # Busca todos os horários brutos apenas dessa semana
        horarios_raw = db.session.query(Horario).filter(
            Horario.semana_id.in_(semana_ids)
        ).all()

        output.append("<table border='1' cellpadding='5'><tr><th>ID Horario</th><th>Dia salvo no Banco</th><th>Pelotão salvo no Horário</th><th>Disciplina ID</th><th>Turma_id da Disc</th></tr>")
        
        for h in horarios_raw:
            disc_turma_id = h.disciplina.turma_id if h.disciplina else "Sem Disciplina"
            
            # Destaca a linha se for o dia que estamos procurando
            is_target_day = "background-color: #ffffcc;" if dia_str[:4].lower() in (h.dia_semana or "").lower() else ""
            
            output.append(f"<tr style='{is_target_day}'>")
            output.append(f"<td>{h.id}</td>")
            output.append(f"<td>'{h.dia_semana}'</td>")
            output.append(f"<td>'{h.pelotao}'</td>")
            output.append(f"<td>{h.disciplina_id}</td>")
            output.append(f"<td>{disc_turma_id}</td>")
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
        aluno = verify_chefe_permission()
        
        if not aluno or not aluno.turma_id:
            flash("Acesso restrito ou aluno sem turma.", "danger")
            return redirect(url_for('main.index'))

        data_str = request.args.get('data')
        data_hoje = get_data_hoje_brasil()
        data_selecionada = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else data_hoje
        
        semanas_ativas = db.session.query(Semana).join(Ciclo).filter(
            Ciclo.school_id == aluno.turma.school_id,
            Ciclo.edicao_id == aluno.turma.edicao_id,
            Semana.data_inicio <= data_selecionada,
            Semana.data_fim >= data_selecionada
        ).all()

        if not semanas_ativas:
            # FALLBACK DE SEGURANÇA: Busca a última semana cadastrada antes dessa data
            fallback_semana = db.session.query(Semana).join(Ciclo).filter(
                Ciclo.school_id == aluno.turma.school_id,
                Ciclo.edicao_id == aluno.turma.edicao_id,
                Semana.data_inicio <= data_selecionada
            ).order_by(Semana.data_inicio.desc()).first()
            
            if fallback_semana:
                semanas_ativas = [fallback_semana]
            else:
                return render_template('chefe/painel.html', aluno=aluno, aulas_agrupadas=[], data_selecionada=data_selecionada, erro_semana=True)

        semana_ids = [s.id for s in semanas_ativas]
        dia_str = get_dia_semana_str(data_selecionada)
        
        variacoes_nome = get_variacoes_nome_turma(aluno.turma.nome)
        
        query = db.session.query(Horario)\
            .outerjoin(Horario.disciplina)\
            .outerjoin(Disciplina.turma)\
            .options(
                joinedload(Horario.disciplina),
                joinedload(Horario.instrutor)
            ).filter(
                Turma.school_id == aluno.turma.school_id,
                Horario.semana_id.in_(semana_ids),
                Horario.dia_semana.ilike(f"{dia_str}%")
            )

        query = query.filter(
            or_(
                Disciplina.turma_id == aluno.turma_id,
                Horario.pelotao == aluno.turma.nome,
                Horario.pelotao.in_(variacoes_nome)
            )
        )
        # CORREÇÃO: Ordem dupla para evitar não-determinismo em períodos idênticos
        horarios = query.order_by(Horario.periodo, Horario.id).all()

        diarios_hoje = db.session.query(DiarioClasse).filter_by(
            data_aula=data_selecionada, 
            turma_id=aluno.turma_id,
            is_deleted=False # IGNORA LIXEIRA AQUI PARA NÃO BLOQUEAR RECRIAR
        ).all()
        
        aulas_concluidas_keys = set()
        for d in diarios_hoje:
            if d.periodo:
                aulas_concluidas_keys.add(f"{d.disciplina_id}_{d.periodo}")
            else:
                aulas_concluidas_keys.add(f"{d.disciplina_id}_legacy")

        # REFACTORING: Agrupamento Inteligente COM DEDUPLICAÇÃO DE BLOCOS SOBREPOSTOS
        flat_periods = []
        seen_periods = set()
        
        if horarios:
            for h in horarios:
                if not h.disciplina:
                    continue
                dur = h.duracao if h.duracao and h.duracao > 0 else 1
                for i in range(dur):
                    p = h.periodo + i
                    key = f"{h.disciplina_id}_{p}"
                    # A DEDUPLICAÇÃO ACONTECE AQUI: Impede que o mesmo período da mesma matéria gere blocos repetidos
                    if key not in seen_periods:
                        flat_periods.append({
                            'periodo': p,
                            'obj': h,
                            'disc_id': h.disciplina_id,
                            'instrutor': h.instrutor
                        })
                        seen_periods.add(key)
                    
        # Ordena todos os períodos do dia cronologicamente
        flat_periods.sort(key=lambda x: x['periodo'])
        
        blocos = []
        current_block = None
        
        for fp in flat_periods:
            if not current_block:
                # Inicializa o primeiro bloco
                nome_instrutor = "N/A"
                if fp['instrutor']:
                    if hasattr(fp['instrutor'], 'user') and fp['instrutor'].user:
                        nome_instrutor = fp['instrutor'].user.nome_de_guerra or fp['instrutor'].user.nome_completo
                    elif hasattr(fp['instrutor'], 'nome_guerra'):
                        nome_instrutor = fp['instrutor'].nome_guerra
                        
                current_block = {
                    'disciplina': fp['obj'].disciplina,
                    'disc_id': fp['disc_id'],
                    'nome_instrutor': nome_instrutor,
                    'horarios_reais': [fp['obj']],
                    'periodos_expandidos': [fp['periodo']],
                    'status': 'pendente',
                    'primeiro_horario_id': fp['obj'].id,
                    'total_tempos': 1,
                    'last_p': fp['periodo']
                }
            else:
                # Verifica se é a mesma disciplina E se é imediatamente consecutivo
                if fp['disc_id'] == current_block['disc_id'] and fp['periodo'] == current_block['last_p'] + 1:
                    current_block['periodos_expandidos'].append(fp['periodo'])
                    current_block['last_p'] = fp['periodo']
                    if fp['obj'] not in current_block['horarios_reais']:
                        current_block['horarios_reais'].append(fp['obj'])
                    current_block['total_tempos'] += 1
                else:
                    # Quebrou a sequência, guarda o atual e cria um novo
                    blocos.append(current_block)
                    
                    nome_instrutor = "N/A"
                    if fp['instrutor']:
                        if hasattr(fp['instrutor'], 'user') and fp['instrutor'].user:
                            nome_instrutor = fp['instrutor'].user.nome_de_guerra or fp['instrutor'].user.nome_completo
                        elif hasattr(fp['instrutor'], 'nome_guerra'):
                            nome_instrutor = fp['instrutor'].nome_guerra
                            
                    current_block = {
                        'disciplina': fp['obj'].disciplina,
                        'disc_id': fp['disc_id'],
                        'nome_instrutor': nome_instrutor,
                        'horarios_reais': [fp['obj']],
                        'periodos_expandidos': [fp['periodo']],
                        'status': 'pendente',
                        'primeiro_horario_id': fp['obj'].id,
                        'total_tempos': 1,
                        'last_p': fp['periodo']
                    }

        if current_block:
            blocos.append(current_block)
            
        # Processa as contagens de conclusão para cada bloco
        for b in blocos:
            b['periodos'] = sorted(list(set(b['periodos_expandidos'])))
            b['tempos_concluidos'] = 0
            for p in b['periodos']:
                key = f"{b['disc_id']}_{p}"
                legacy_key = f"{b['disc_id']}_legacy"
                if key in aulas_concluidas_keys or legacy_key in aulas_concluidas_keys:
                    b['tempos_concluidos'] += 1
                    
            if b['tempos_concluidos'] >= b['total_tempos'] and b['total_tempos'] > 0:
                b['status'] = 'concluido'
                
            aulas_agrupadas.append(b)

        return render_template('chefe/painel.html', aluno=aluno, aulas_agrupadas=aulas_agrupadas, data_selecionada=data_selecionada, erro_semana=False)

    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"Erro no painel: {str(e)}", "danger")
        return redirect(url_for('main.index'))

@chefe_bp.route('/registrar/<int:primeiro_horario_id>', methods=['GET', 'POST'])
@login_required
def registrar_aula(primeiro_horario_id):
    try:
        aluno_chefe = verify_chefe_permission()
        if not aluno_chefe: return redirect(url_for('main.index'))

        horario_base = db.session.query(Horario)\
            .outerjoin(Horario.disciplina)\
            .outerjoin(Disciplina.turma)\
            .filter(
                Horario.id == primeiro_horario_id,
                Turma.school_id == aluno_chefe.turma.school_id
            ).first()

        if not horario_base: 
            flash("Horário não encontrado ou não pertence à sua escola.", "danger")
            return redirect(url_for('chefe.painel'))

        data_str = request.args.get('data')
        data_hoje = get_data_hoje_brasil()
        data_aula = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else data_hoje

        variacoes_nome = get_variacoes_nome_turma(aluno_chefe.turma.nome)
        
        # Busca apenas os horários DESTA disciplina neste dia para formar os blocos de validação
        horarios_db = db.session.query(Horario)\
            .outerjoin(Horario.disciplina)\
            .outerjoin(Disciplina.turma)\
            .filter(
                Turma.school_id == aluno_chefe.turma.school_id,
                Horario.semana_id == horario_base.semana_id,
                Horario.dia_semana == horario_base.dia_semana,
                Horario.disciplina_id == horario_base.disciplina_id,
                or_(
                    Disciplina.turma_id == aluno_chefe.turma_id,
                    Horario.pelotao == aluno_chefe.turma.nome,
                    Horario.pelotao.in_(variacoes_nome)
                )
            ).order_by(Horario.periodo).all()

        # Reconstrói os blocos consecutivos idênticos ao painel para encontrar onde a aula se encaixa
        flat_periods = []
        for h in horarios_db:
            dur = h.duracao if h.duracao and h.duracao > 0 else 1
            for i in range(dur):
                flat_periods.append({'periodo': h.periodo + i, 'obj': h})
        
        flat_periods.sort(key=lambda x: x['periodo'])
        
        blocos = []
        current_block = None
        for fp in flat_periods:
            if not current_block:
                current_block = {'horarios_reais': [fp['obj']], 'periodos_expandidos': [fp['periodo']], 'last_p': fp['periodo']}
            else:
                if fp['periodo'] == current_block['last_p'] + 1:
                    current_block['periodos_expandidos'].append(fp['periodo'])
                    current_block['last_p'] = fp['periodo']
                    if fp['obj'] not in current_block['horarios_reais']:
                        current_block['horarios_reais'].append(fp['obj'])
                else:
                    blocos.append(current_block)
                    current_block = {'horarios_reais': [fp['obj']], 'periodos_expandidos': [fp['periodo']], 'last_p': fp['periodo']}
        if current_block:
            blocos.append(current_block)
            
        # Encontrar o bloco exato que contém o horário que o usuário clicou para assinar
        target_block = None
        for b in blocos:
            if any(h.id == primeiro_horario_id for h in b['horarios_reais']):
                target_block = b
                break
                
        if not target_block:
            flash("Horário não encontrado nos blocos do dia.", "danger")
            return redirect(url_for('chefe.painel', data=data_aula))
            
        # Agora a trava respeita o FIM DESTE BLOCO e não o fim do dia!
        ultimo_periodo_real_do_bloco = target_block['last_p']
        
        horarios_expandidos = []
        periodos_processados = set() 

        for p in target_block['periodos_expandidos']:
            horario_pai = next(h for h in target_block['horarios_reais'] if h.periodo <= p < h.periodo + (h.duracao or 1))
            
            existe = db.session.query(DiarioClasse).filter_by(
                data_aula=data_aula,
                turma_id=aluno_chefe.turma_id,
                disciplina_id=horario_base.disciplina_id,
                periodo=p,
                is_deleted=False 
            ).first()
            
            if not existe:
                if p not in periodos_processados:
                    horarios_expandidos.append({'periodo': p, 'horario_pai_id': horario_pai.id, 'obj': horario_pai})
                    periodos_processados.add(p) 
        
        horarios_expandidos.sort(key=lambda x: x['periodo'])
        
        if not horarios_expandidos:
            flash("Todas as aulas desta disciplina já foram registradas para hoje.", "info")
            return redirect(url_for('chefe.painel', data=data_aula))

        # CORREÇÃO APLICADA AQUI: Filtrar apenas usuários ativos e com papel estrito de 'aluno'
        alunos_turma = db.session.query(Aluno).join(User, Aluno.user_id == User.id).filter(
            Aluno.turma_id == aluno_chefe.turma_id,
            User.is_active == True,
            User.role == 'aluno'
        ).order_by(Aluno.num_aluno).all()

        if request.method == 'POST':
            conteudo_informado = request.form.get('conteudo')
            
            ok_cont, msg_cont = DiarioService.validar_conteudo_obrigatorio(conteudo_informado)
            if not ok_cont:
                flash(msg_cont, "danger")
                return redirect(request.url)

            # Validação de Horário adaptada para verificar o fim EXATO daquele bloco isolado
            periodos_para_registrar = [h['periodo'] for h in horarios_expandidos]
            if periodos_para_registrar:
                ok_hora, msg_hora = DiarioService.validar_criacao_diario_aluno(data_aula, ultimo_periodo_real_do_bloco)
                if not ok_hora:
                    flash(msg_hora, "danger")
                    return redirect(request.url)

            try:
                ids_horarios_pais_atualizados = set()
                count_regs = 0
                for h_virt in horarios_expandidos:
                    periodo_atual = h_virt['periodo']
                    horario_pai = h_virt['obj']

                    ja_salvo_agora = db.session.query(DiarioClasse).filter_by(
                        data_aula=data_aula,
                        turma_id=aluno_chefe.turma_id,
                        disciplina_id=horario_pai.disciplina_id,
                        periodo=periodo_atual,
                        is_deleted=False
                    ).first()

                    if ja_salvo_agora:
                        continue 

                    novo_diario = DiarioClasse(
                        data_aula=data_aula,
                        turma_id=aluno_chefe.turma_id,
                        disciplina_id=horario_pai.disciplina_id,
                        responsavel_id=current_user.id,
                        observacoes=request.form.get('observacoes'),
                        conteudo_ministrado=conteudo_informado, 
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
                return redirect(url_for('chefe.painel', data=data_aula))
            except Exception as e:
                db.session.rollback()
                flash(f"Erro ao salvar: {str(e)}", "danger")

        nome_instrutor = "N/A"
        if horario_base.instrutor:
             if hasattr(horario_base.instrutor, 'user') and horario_base.instrutor.user:
                 nome_instrutor = horario_base.instrutor.user.nome_de_guerra
        
        return render_template('chefe/registrar.html', horarios=horarios_expandidos, disciplina=horario_base.disciplina, nome_instrutor=nome_instrutor, alunos=alunos_turma, data_aula=data_aula)

    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"Erro: {str(e)}", "danger")
        return redirect(url_for('chefe.painel'))
