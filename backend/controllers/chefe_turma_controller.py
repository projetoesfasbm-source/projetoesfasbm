from flask import Blueprint, render_template, request, flash, redirect, url_for, g, current_app
from flask_login import login_required, current_user
from datetime import date, datetime
from sqlalchemy import select, text
from sqlalchemy.orm import joinedload 

from backend.models.database import db
from backend.models.horario import Horario
from backend.models.aluno import Aluno
from backend.models.turma_cargo import TurmaCargo 
from backend.models.diario_classe import DiarioClasse
from backend.models.frequencia import FrequenciaAluno
from backend.models.semana import Semana

chefe_bp = Blueprint('chefe', __name__, url_prefix='/chefe')

def verify_chefe_permission():
    try:
        if not current_user.is_authenticated or not current_user.aluno_profile:
            return None
        aluno = current_user.aluno_profile
        return aluno
    except Exception as e:
        print(f"[DEBUG] Erro ao verificar permissao: {e}")
        return None

@chefe_bp.route('/debug')
@login_required
def debug_screen():
    """
    Rota de diagnóstico para identificar por que as aulas não aparecem.
    Acessível via /chefe/debug
    """
    output = []
    output.append("<h1>Diagnóstico do Painel de Chefe (v2)</h1>")
    
    try:
        aluno = current_user.aluno_profile
        if not aluno:
            return "ERRO CRÍTICO: Usuário logado não possui perfil de aluno vinculado."
        
        # CORREÇÃO: Acessa o nome através do relacionamento .user
        nome_aluno = "Nome não encontrado"
        if aluno.user:
            nome_aluno = getattr(aluno.user, 'nome_completo', 'Sem atributo nome_completo')
            
        output.append(f"<h3>1. Dados do Aluno</h3>")
        output.append(f"Aluno ID: {aluno.id} - Nome: {nome_aluno}")
        
        if not aluno.turma:
            output.append("<p style='color:red'>ERRO: Aluno não está vinculado a nenhuma turma (aluno.turma is None).</p>")
        else:
            output.append(f"<p>Turma Vinculada: <strong>'{aluno.turma.nome}'</strong> (ID: {aluno.turma_id})</p>")
            
        data_hoje = date.today()
        output.append(f"<h3>2. Verificação de Data e Semana</h3>")
        output.append(f"<p>Data de Hoje: {data_hoje}</p>")
        
        semana_ativa = db.session.query(Semana).filter(
            Semana.data_inicio <= data_hoje,
            Semana.data_fim >= data_hoje
        ).first()
        
        if not semana_ativa:
            output.append(f"<p style='color:red'>ERRO: Nenhuma 'Semana' cadastrada no banco cobre a data de hoje ({data_hoje}). O sistema não sabe qual semana letiva é.</p>")
            proxima_semana = db.session.query(Semana).filter(Semana.data_inicio > data_hoje).order_by(Semana.data_inicio).first()
            if proxima_semana:
                output.append(f"<p>Próxima semana cadastrada começa em: {proxima_semana.data_inicio}</p>")
        else:
            output.append(f"<p style='color:green'>SUCESSO: Semana encontrada (ID: {semana_ativa.id}) - De {semana_ativa.data_inicio} a {semana_ativa.data_fim}</p>")
            
            dias_semana = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
            dia_str = dias_semana[data_hoje.weekday()]
            output.append(f"<p>Dia da semana calculado: <strong>{dia_str}</strong></p>")
            
            output.append(f"<h3>3. Busca de Horários</h3>")
            
            if aluno.turma:
                # Query exata
                qtd_exata = db.session.query(Horario).filter_by(
                    pelotao=aluno.turma.nome,
                    semana_id=semana_ativa.id,
                    dia_semana=dia_str
                ).count()
                
                msg_cor = 'green' if qtd_exata > 0 else 'red'
                output.append(f"<p style='color:{msg_cor}'>Busca exata por pelotao='{aluno.turma.nome}': Encontrados <strong>{qtd_exata}</strong> horários.</p>")
                
                if qtd_exata == 0:
                    output.append("<p><strong>Investigação de Falha:</strong> Listando turmas que POSSUEM aula hoje no banco:</p>")
                    pelotoes_com_aula = db.session.query(Horario.pelotao).filter_by(
                        semana_id=semana_ativa.id,
                        dia_semana=dia_str
                    ).distinct().all()
                    
                    lista_pelotoes = [p[0] for p in pelotoes_com_aula]
                    output.append(f"<p>Turmas com aula hoje: {lista_pelotoes}</p>")
                    output.append(f"<p><em>Compare o nome '{aluno.turma.nome}' com a lista acima. Diferenças minúsculas (espaço, acento) impedem a visualização.</em></p>")

    except Exception as e:
        import traceback
        output.append(f"<h3 style='color:red'>EXCEÇÃO OCORRIDA NO DEBUG:</h3>")
        output.append(f"<pre>{traceback.format_exc()}</pre>")

    return "<br>".join(output)

@chefe_bp.route('/painel')
@login_required
def painel():
    try:
        aulas_agrupadas = []
        print("[DEBUG] Iniciando painel chefe")
        
        aluno = verify_chefe_permission()
        if not aluno:
            flash("Acesso restrito.", "danger")
            return redirect(url_for('main.index'))

        if not aluno.turma_id or not aluno.turma:
            flash("Erro: Aluno sem turma.", "warning")
            return redirect(url_for('main.index'))

        # CORREÇÃO: Acessa o nome corretamente para o log
        nome_debug = aluno.user.nome_completo if aluno.user else "User N/A"
        print(f"[DEBUG] Aluno: {nome_debug}, Turma: {aluno.turma.nome}")

        data_str = request.args.get('data')
        data_selecionada = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else date.today()
        
        semana_ativa = db.session.query(Semana).filter(
            Semana.data_inicio <= data_selecionada,
            Semana.data_fim >= data_selecionada
        ).first()

        if not semana_ativa:
            return render_template('chefe/painel.html', 
                                   aluno=aluno, aulas_agrupadas=[], 
                                   data_selecionada=data_selecionada, erro_semana=True)

        dias_semana = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        dia_str = dias_semana[data_selecionada.weekday()]
        
        # Query principal restaurada (Baseada em String do Pelotão)
        horarios = db.session.query(Horario).options(
            joinedload(Horario.disciplina),
            joinedload(Horario.instrutor)
        ).filter_by(
            pelotao=aluno.turma.nome,
            semana_id=semana_ativa.id,
            dia_semana=dia_str
        ).order_by(Horario.periodo).all()

        print(f"[DEBUG] Horarios encontrados: {len(horarios)}")

        # Verificar diários feitos HOJE
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

        return render_template('chefe/painel.html', 
                               aluno=aluno, 
                               aulas_agrupadas=aulas_agrupadas, 
                               data_selecionada=data_selecionada,
                               erro_semana=False)

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

        horario_base = db.session.get(Horario, primeiro_horario_id)
        if not horario_base: return redirect(url_for('chefe.painel'))

        data_str = request.args.get('data')
        data_aula = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else date.today()

        horarios_db = db.session.query(Horario).filter_by(
            pelotao=aluno_chefe.turma.nome,
            semana_id=horario_base.semana_id,
            dia_semana=horario_base.dia_semana,
            disciplina_id=horario_base.disciplina_id
        ).order_by(Horario.periodo).all()

        horarios_expandidos = []
        for h in horarios_db:
            duracao = h.duracao if h.duracao and h.duracao > 0 else 1
            for i in range(duracao):
                p = h.periodo + i
                horarios_expandidos.append({
                    'periodo': p,
                    'horario_pai_id': h.id, 
                    'obj': h
                })
        
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
                        
                        db.session.add(FrequenciaAluno(
                            diario_id=novo_diario.id, 
                            aluno_id=aluno.id, 
                            presente=presente
                        ))
                    
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
        
        return render_template('chefe/registrar.html', 
                               horarios=horarios_expandidos, 
                               disciplina=horario_base.disciplina,
                               nome_instrutor=nome_instrutor, 
                               alunos=alunos_turma, 
                               data_aula=data_aula)

    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"Erro: {str(e)}", "danger")
        return redirect(url_for('chefe.painel'))