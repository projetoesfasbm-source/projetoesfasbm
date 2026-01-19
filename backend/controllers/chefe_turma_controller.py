from flask import Blueprint, render_template, request, flash, redirect, url_for, g
from flask_login import login_required, current_user
from datetime import date, datetime
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import joinedload 
import re

from backend.models.database import db
from backend.models.horario import Horario
from backend.models.aluno import Aluno
from backend.models.turma_cargo import TurmaCargo 
from backend.models.diario_classe import DiarioClasse
from backend.models.frequencia import FrequenciaAluno
from backend.models.semana import Semana
from backend.models.disciplina import Disciplina
from backend.models.turma import Turma  # Import essencial para o filtro de escola

chefe_bp = Blueprint('chefe', __name__, url_prefix='/chefe')

def get_variacoes_nome_turma(nome_original):
    """Gera variações comuns de nomes de turma para busca flexível."""
    variacoes = {nome_original}
    try:
        match = re.search(r'(\d+)', nome_original)
        if match:
            num_str = match.group(1)
            num_int = int(num_str)
            variacoes.add(f"Turma {num_str}")      # "Turma 01"
            variacoes.add(f"Turma {num_int}")      # "Turma 1"
            variacoes.add(f"{num_str}º Pelotão")   # "01º Pelotão"
            variacoes.add(f"{num_int}º Pelotão")   # "1º Pelotão"
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
    output.append("<h1>Diagnóstico: Raio-X com Filtro de Escola</h1>")
    
    try:
        aluno = current_user.aluno_profile
        if not aluno or not aluno.turma:
            return "Erro: Aluno sem turma vinculada."
            
        escola_id = aluno.turma.school_id
        output.append(f"<h3>1. Perfil e Contexto</h3>")
        output.append(f"<ul><li><strong>Aluno:</strong> {aluno.user.nome_completo}</li>")
        output.append(f"<li><strong>Sua Turma:</strong> '{aluno.turma.nome}' (ID: {aluno.turma_id})</li>")
        output.append(f"<li><strong>Sua Escola (SchoolID):</strong> <span style='color:blue; font-size:1.2em'><b>{escola_id}</b></span></li></ul>")
        
        data_hoje = date.today()
        semana = db.session.query(Semana).filter(Semana.data_inicio <= data_hoje, Semana.data_fim >= data_hoje).first()
        
        if not semana:
            output.append("<h3 style='color:red'>ERRO: Nenhuma semana letiva ativa hoje!</h3>")
            return "<br>".join(output)
            
        dias = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        dia_str = dias[data_hoje.weekday()]
        
        output.append(f"<h3>2. Varredura Segura ({dia_str})</h3>")
        output.append(f"<p>Buscando aulas SOMENTE na escola <strong>{escola_id}</strong>...</p>")
        
        # Busca todas as aulas do dia, mas FILTRANDO pela escola
        horarios = db.session.query(Horario).join(Horario.disciplina).join(Disciplina.turma).filter(
            Turma.school_id == escola_id, # <--- TRAVA DE SEGURANÇA
            Horario.semana_id == semana.id, 
            Horario.dia_semana == dia_str
        ).all()
        
        output.append("<table border='1' cellpadding='5' style='width:100%; border-collapse:collapse'>")
        output.append("<tr style='background:#f0f0f0'><th>ID Aula</th><th>Matéria</th><th>Turma da Aula</th><th>School ID</th><th>Compatível com Você?</th></tr>")
        
        if not horarios:
            output.append("<tr><td colspan='5' style='text-align:center'>Nenhuma aula encontrada nesta escola para hoje.</td></tr>")
        
        for h in horarios:
            disc_turma = h.disciplina.turma
            
            # Verifica compatibilidade
            eh_minha_turma = (disc_turma.id == aluno.turma_id)
            eh_meu_nome = (h.pelotao == aluno.turma.nome) or (h.pelotao in get_variacoes_nome_turma(aluno.turma.nome))
            
            cor = "#dff0d8" if (eh_minha_turma or eh_meu_nome) else "#fff"
            status = "<b>SIM</b>" if (eh_minha_turma or eh_meu_nome) else "Não (Outra turma desta escola)"
            
            output.append(f"<tr style='background:{cor}'>")
            output.append(f"<td>{h.id}</td>")
            output.append(f"<td>{h.disciplina.materia}</td>")
            output.append(f"<td>{disc_turma.nome} (ID: {disc_turma.id})</td>")
            output.append(f"<td>{disc_turma.school_id}</td>")
            output.append(f"<td>{status}</td>")
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
        data_selecionada = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else date.today()
        
        semana_ativa = db.session.query(Semana).filter(
            Semana.data_inicio <= data_selecionada,
            Semana.data_fim >= data_selecionada
        ).first()

        if not semana_ativa:
            return render_template('chefe/painel.html', aluno=aluno, aulas_agrupadas=[], data_selecionada=data_selecionada, erro_semana=True)

        dias_semana = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        dia_str = dias_semana[data_selecionada.weekday()]
        
        # --- BUSCA SEGURA (COM TRAVA DE ESCOLA) ---
        variacoes_nome = get_variacoes_nome_turma(aluno.turma.nome)
        
        # O JOIN com Turma permite filtrar Turma.school_id
        horarios = db.session.query(Horario).join(Horario.disciplina).join(Disciplina.turma).options(
            joinedload(Horario.disciplina),
            joinedload(Horario.instrutor)
        ).filter(
            Turma.school_id == aluno.turma.school_id,   # <--- TRAVA CRÍTICA DE SEGURANÇA
            Horario.semana_id == semana_ativa.id,
            Horario.dia_semana == dia_str,
            or_(
                Disciplina.turma_id == aluno.turma_id,
                Horario.pelotao == aluno.turma.nome,
                Horario.pelotao.in_(variacoes_nome)
            )
        ).order_by(Horario.periodo).all()

        diarios_hoje = db.session.query(DiarioClasse).filter_by(
            data_aula=data_selecionada, 
            turma_id=aluno.turma_id
        ).all()
        disciplinas_concluidas = set([d.disciplina_id for d in diarios_hoje])

        grupos_dict = {}
        if horarios:
            for h in horarios:
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
                        'primeiro_horario_id': h.id
                    }
                
                grupos_dict[disc_id]['horarios_reais'].append(h)
                duracao = h.duracao if h.duracao and h.duracao > 0 else 1
                for i in range(duracao):
                    periodo_real = h.periodo + i
                    grupos_dict[disc_id]['periodos_expandidos'].append(periodo_real)
                
                if h.status == 'concluido' or disc_id in disciplinas_concluidas:
                    grupos_dict[disc_id]['status'] = 'concluido'

            for g in sorted(grupos_dict.values(), key=lambda x: min(x['periodos_expandidos'])):
                g['periodos'] = sorted(list(set(g['periodos_expandidos'])))
                aulas_agrupadas.append(g)

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

        # Carrega o horário garantindo que pertence à mesma escola (via disciplina -> turma)
        horario_base = db.session.query(Horario).join(Horario.disciplina).join(Disciplina.turma).filter(
            Horario.id == primeiro_horario_id,
            Turma.school_id == aluno_chefe.turma.school_id # <--- VERIFICAÇÃO DE SEGURANÇA
        ).first()

        if not horario_base: 
            flash("Horário não encontrado ou não pertence à sua escola.", "danger")
            return redirect(url_for('chefe.painel'))

        data_str = request.args.get('data')
        data_aula = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else date.today()

        variacoes_nome = get_variacoes_nome_turma(aluno_chefe.turma.nome)
        
        # Busca os outros tempos com a mesma trava de segurança
        horarios_db = db.session.query(Horario).join(Horario.disciplina).join(Disciplina.turma).filter(
            Turma.school_id == aluno_chefe.turma.school_id, # <--- TRAVA
            Horario.semana_id == horario_base.semana_id,
            Horario.dia_semana == horario_base.dia_semana,
            Horario.disciplina_id == horario_base.disciplina_id,
            or_(
                Disciplina.turma_id == aluno_chefe.turma_id,
                Horario.pelotao == aluno_chefe.turma.nome,
                Horario.pelotao.in_(variacoes_nome)
            )
        ).order_by(Horario.periodo).all()

        horarios_expandidos = []
        for h in horarios_db:
            duracao = h.duracao if h.duracao and h.duracao > 0 else 1
            for i in range(duracao):
                p = h.periodo + i
                horarios_expandidos.append({'periodo': p, 'horario_pai_id': h.id, 'obj': h})
        
        horarios_expandidos.sort(key=lambda x: x['periodo'])
        alunos_turma = db.session.query(Aluno).filter_by(turma_id=aluno_chefe.turma_id).order_by(Aluno.num_aluno).all()

        if request.method == 'POST':
            try:
                ids_horarios_pais_atualizados = set()
                for h_virt in horarios_expandidos:
                    periodo_atual = h_virt['periodo']
                    horario_pai = h_virt['obj']

                    novo_diario = DiarioClasse(
                        data_aula=data_aula,
                        turma_id=aluno_chefe.turma_id,
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

                db.session.commit()
                flash(f"Salvo com sucesso! {len(horarios_expandidos)} tempos registrados.", "success")
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