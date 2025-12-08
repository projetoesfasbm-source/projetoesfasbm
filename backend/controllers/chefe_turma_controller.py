# backend/controllers/chefe_turma_controller.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, g
from flask_login import login_required, current_user
from datetime import date, datetime
from sqlalchemy import select, and_
from sqlalchemy.orm import joinedload # Importante para trazer os dados juntos

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
        cargo_chefe = db.session.query(TurmaCargo).filter_by(
            aluno_id=aluno.id,
            cargo_nome=TurmaCargo.ROLE_CHEFE
        ).first()
        
        if cargo_chefe:
            return aluno
        return None
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
            flash("Erro: Aluno sem turma vinculada.", "warning")
            return redirect(url_for('main.index'))

        # Data
        data_str = request.args.get('data')
        if data_str:
            data_selecionada = datetime.strptime(data_str, '%Y-%m-%d').date()
        else:
            data_selecionada = date.today()

        # Busca Semana
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
        
        # BUSCA OTIMIZADA COM JOIN (Garante que traga Disciplina e Instrutor)
        horarios = db.session.query(Horario).options(
            joinedload(Horario.disciplina),
            joinedload(Horario.instrutor)
        ).filter_by(
            pelotao=aluno.turma.nome,
            semana_id=semana_ativa.id,
            dia_semana=dia_str
        ).order_by(Horario.periodo).all()

        # Verificar diários feitos
        diarios_hoje = db.session.query(DiarioClasse).filter_by(
            data_aula=data_selecionada, 
            turma_id=aluno.turma_id
        ).all()
        disciplinas_feitas_ids = set([d.disciplina_id for d in diarios_hoje])

        # Agrupamento
        aulas_agrupadas = []
        if horarios:
            grupo_atual = None
            for h in horarios:
                if grupo_atual and h.disciplina_id == grupo_atual['disciplina'].id:
                    grupo_atual['horarios'].append(h)
                    grupo_atual['periodos'].append(h.periodo)
                else:
                    if grupo_atual: aulas_agrupadas.append(grupo_atual)
                    
                    # Tenta pegar o nome do instrutor de forma segura
                    nome_instrutor = "N/A"
                    if h.instrutor:
                        # Tenta pegar do usuário vinculado, se não, pega do próprio instrutor se tiver campo nome
                        if hasattr(h.instrutor, 'user') and h.instrutor.user:
                            nome_instrutor = h.instrutor.user.nome_de_guerra or h.instrutor.user.nome_completo
                        elif hasattr(h.instrutor, 'nome_guerra'): # Caso seu model Instrutor tenha o campo direto
                            nome_instrutor = h.instrutor.nome_guerra
                    
                    status = 'concluido' if h.disciplina_id in disciplinas_feitas_ids else 'pendente'
                    
                    grupo_atual = {
                        'disciplina': h.disciplina,
                        'nome_instrutor': nome_instrutor, # Passa string pronta
                        'horarios': [h], 
                        'periodos': [h.periodo],
                        'status': status,
                        'primeiro_horario_id': h.id 
                    }
            if grupo_atual: aulas_agrupadas.append(grupo_atual)

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

        horarios_grupo = db.session.query(Horario).filter_by(
            pelotao=aluno_chefe.turma.nome,
            semana_id=horario_base.semana_id,
            dia_semana=horario_base.dia_semana,
            disciplina_id=horario_base.disciplina_id
        ).order_by(Horario.periodo).all()

        alunos_turma = db.session.query(Aluno).filter_by(turma_id=aluno_chefe.turma_id).order_by(Aluno.num_aluno).all()

        if request.method == 'POST':
            try:
                for h in horarios_grupo:
                    novo_diario = DiarioClasse(
                        data_aula=data_aula,
                        turma_id=aluno_chefe.turma_id,
                        disciplina_id=h.disciplina_id,
                        responsavel_id=current_user.id,
                        observacoes=request.form.get('observacoes'),
                        conteudo_ministrado=request.form.get('conteudo')
                    )
                    db.session.add(novo_diario)
                    db.session.flush()

                    for aluno in alunos_turma:
                        presente = request.form.get(f'presenca_{aluno.id}_{h.periodo}') == 'on'
                        db.session.add(FrequenciaAluno(diario_id=novo_diario.id, aluno_id=aluno.id, presente=presente))
                
                db.session.commit()
                flash(f"Salvo com sucesso!", "success")
                return redirect(url_for('chefe.painel', data=data_aula))
            except Exception as e:
                db.session.rollback()
                flash(f"Erro: {str(e)}", "danger")

        # Nome do instrutor para o template de registro
        nome_instrutor = "N/A"
        if horario_base.instrutor:
             if hasattr(horario_base.instrutor, 'user') and horario_base.instrutor.user:
                 nome_instrutor = horario_base.instrutor.user.nome_de_guerra
        
        return render_template('chefe/registrar.html', 
                               horarios=horarios_grupo, 
                               disciplina=horario_base.disciplina,
                               nome_instrutor=nome_instrutor, # Passa string
                               alunos=alunos_turma, 
                               data_aula=data_aula)

    except Exception as e:
        flash(f"Erro: {str(e)}", "danger")
        return redirect(url_for('chefe.painel'))