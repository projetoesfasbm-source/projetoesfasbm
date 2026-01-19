from flask import Blueprint, render_template, request, flash, redirect, url_for, g
from flask_login import login_required, current_user
from datetime import date, datetime
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import joinedload 

from backend.models.database import db
from backend.models.horario import Horario
from backend.models.aluno import Aluno
from backend.models.turma_cargo import TurmaCargo 
from backend.models.diario_classe import DiarioClasse
from backend.models.frequencia import FrequenciaAluno
from backend.models.semana import Semana
from backend.models.ciclo import Ciclo  # IMPORTAÇÃO NECESSÁRIA

chefe_bp = Blueprint('chefe', __name__, url_prefix='/chefe')

def verify_chefe_permission():
    try:
        if not current_user.is_authenticated or not current_user.aluno_profile:
            return None
        aluno = current_user.aluno_profile
        cargo_chefe = db.session.query(TurmaCargo).filter_by(
            aluno_id=aluno.id,
            cargo_nome=TurmaCargo.ROLE_CHEFE
        ).first()
        return aluno if cargo_chefe else None
    except Exception:
        return None

@chefe_bp.route('/painel')
@login_required
def painel():
    try:
        aluno = verify_chefe_permission()
        if not aluno:
            flash("Acesso restrito.", "danger")
            return redirect(url_for('main.index'))

        if not aluno.turma_id or not aluno.turma:
            flash("Erro: Aluno sem turma.", "warning")
            return redirect(url_for('main.index'))

        data_str = request.args.get('data')
        data_selecionada = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else date.today()

        # --- CORREÇÃO CRÍTICA AQUI ---
        # Antes: Buscava qualquer semana no banco (pegava sempre a da Escola 1)
        # Agora: Busca a semana vinculada ao CICLO da ESCOLA do aluno
        semana_ativa = db.session.query(Semana).join(Semana.ciclo).filter(
            Ciclo.school_id == aluno.turma.school_id,  # FILTRO DE ESCOLA OBRIGATÓRIO
            Semana.data_inicio <= data_selecionada,
            Semana.data_fim >= data_selecionada
        ).first()

        if not semana_ativa:
            return render_template('chefe/painel.html', 
                                   aluno=aluno, aulas_agrupadas=[], 
                                   data_selecionada=data_selecionada, erro_semana=True)

        dias_semana = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        dia_str = dias_semana[data_selecionada.weekday()]
        
        # Busca horários usando a semana correta da escola correta
        horarios = db.session.query(Horario).options(
            joinedload(Horario.disciplina),
            joinedload(Horario.instrutor)
        ).filter_by(
            pelotao=aluno.turma.nome, # Busca pelo nome (string) conforme sua configuração
            semana_id=semana_ativa.id,
            dia_semana=dia_str
        ).order_by(Horario.periodo).all()

        # Verificar diários feitos HOJE
        diarios_hoje = db.session.query(DiarioClasse).filter_by(
            data_aula=data_selecionada, 
            turma_id=aluno.turma_id
        ).all()
        
        disciplinas_concluidas = set([d.disciplina_id for d in diarios_hoje])

        # --- AGRUPAMENTO ---
        grupos_dict = {}
        aulas_agrupadas = [] # Inicializa vazio para evitar erro
        
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

        # Busca outros tempos da mesma aula
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