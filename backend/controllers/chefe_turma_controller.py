# backend/controllers/chefe_turma_controller.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, g
from flask_login import login_required, current_user
from datetime import date
from sqlalchemy import select

from backend.models.database import db
from backend.models.horario import Horario
from backend.models.aluno import Aluno
from backend.models.turma_cargo import TurmaCargo 
from backend.models.diario_classe import DiarioClasse
from backend.models.frequencia import FrequenciaAluno

chefe_bp = Blueprint('chefe', __name__, url_prefix='/chefe')

def verify_chefe_permission():
    """
    Verifica se o usuário é aluno E se possui o cargo exato de CHEFE DE TURMA.
    """
    try:
        if not current_user.is_authenticated or not current_user.aluno_profile:
            return None
        
        aluno = current_user.aluno_profile
        
        # BUSCA EXATA PELA CONSTANTE DO MODELO
        cargo_chefe = db.session.query(TurmaCargo).filter_by(
            aluno_id=aluno.id,
            cargo_nome=TurmaCargo.ROLE_CHEFE
        ).first()
        
        if cargo_chefe:
            return aluno
            
        return None
    except Exception as e:
        print(f"Erro Auth Chefe: {e}")
        return None

@chefe_bp.route('/debug')
@login_required
def debug_permissao():
    try:
        if not current_user.aluno_profile: return "Não é aluno."
        aluno = current_user.aluno_profile
        cargos = db.session.query(TurmaCargo).filter_by(aluno_id=aluno.id).all()
        
        # CORREÇÃO AQUI: trocado nome_guerra por nome_de_guerra (conforme seu user.py)
        html = f"<h3>Diagnóstico do Aluno: {current_user.nome_de_guerra} (ID {aluno.id})</h3>"
        html += f"<p>Turma Vinculada: <strong>{aluno.turma.nome if aluno.turma else 'NENHUMA'}</strong></p>"
        html += f"<p>Cargo Esperado: <strong>'{TurmaCargo.ROLE_CHEFE}'</strong></p>"
        html += "<hr><ul>"
        if not cargos: html += "<li style='color:red'>SEM CARGOS VINCULADOS</li>"
        for c in cargos:
            match = (c.cargo_nome == TurmaCargo.ROLE_CHEFE)
            cor = 'green' if match else 'red'
            html += f"<li style='color:{cor}'>Cargo no Banco: '{c.cargo_nome}' - {'VÁLIDO' if match else 'INVÁLIDO'}</li>"
        html += "</ul><a href='/'>Voltar</a>"
        return html
    except Exception as e: return f"Erro debug: {str(e)}"

@chefe_bp.route('/painel')
@login_required
def painel():
    try:
        aluno = verify_chefe_permission()
        if not aluno:
            flash("Acesso restrito. O sistema não identificou o cargo 'Chefe de Turma' para seu usuário.", "danger")
            return redirect(url_for('main.index'))

        if not aluno.turma_id or not aluno.turma:
            flash("Erro: Aluno sem turma vinculada.", "warning")
            return redirect(url_for('main.index'))

        hoje = date.today()
        # Mapeamento Dia da Semana
        dia_semana_map = {0: 'Segunda', 1: 'Terça', 2: 'Quarta', 3: 'Quinta', 4: 'Sexta', 5: 'Sábado', 6: 'Domingo'}
        dia_str = dia_semana_map[hoje.weekday()]
        
        # CORREÇÃO AQUI: trocado dia_da_semana por dia_semana (conforme seu horario.py)
        aulas_hoje = db.session.query(Horario).filter_by(
            pelotao=aluno.turma.nome, 
            dia_semana=dia_str 
        ).order_by(Horario.periodo).all()

        diarios_preenchidos = db.session.query(DiarioClasse).filter_by(
            data_aula=hoje, turma_id=aluno.turma_id
        ).all()
        ids_disciplinas_feitas = [d.disciplina_id for d in diarios_preenchidos]

        return render_template('chefe/painel.html', 
                               aluno=aluno, aulas=aulas_hoje, 
                               feitos=ids_disciplinas_feitas, data_hoje=hoje)
    except Exception as e:
        flash(f"Erro no painel: {str(e)}", "danger")
        return redirect(url_for('main.index'))

@chefe_bp.route('/registrar/<int:horario_id>', methods=['GET', 'POST'])
@login_required
def registrar_aula(horario_id):
    try:
        aluno_chefe = verify_chefe_permission()
        if not aluno_chefe:
            flash("Permissão negada.", "danger")
            return redirect(url_for('main.index'))

        horario = db.session.get(Horario, horario_id)
        
        if not horario or horario.pelotao != aluno_chefe.turma.nome:
            flash("Horário inválido ou pertence a outra turma.", "danger")
            return redirect(url_for('chefe.painel'))
            
        if db.session.query(DiarioClasse).filter_by(data_aula=date.today(), turma_id=aluno_chefe.turma_id, disciplina_id=horario.disciplina_id).first():
            flash("Chamada já realizada.", "warning")
            return redirect(url_for('chefe.painel'))

        alunos_turma = db.session.query(Aluno).filter_by(turma_id=aluno_chefe.turma_id).order_by(Aluno.num_aluno).all()

        if request.method == 'POST':
            try:
                novo_diario = DiarioClasse(
                    data_aula=date.today(),
                    turma_id=aluno_chefe.turma_id,
                    disciplina_id=horario.disciplina_id,
                    responsavel_id=current_user.id,
                    observacoes=request.form.get('observacoes'),
                    conteudo_ministrado=request.form.get('conteudo')
                )
                db.session.add(novo_diario)
                db.session.flush()

                for aluno in alunos_turma:
                    presente = request.form.get(f'presenca_{aluno.id}') == 'on'
                    db.session.add(FrequenciaAluno(diario_id=novo_diario.id, aluno_id=aluno.id, presente=presente))
                
                db.session.commit()
                flash("Registrado com sucesso!", "success")
                return redirect(url_for('chefe.painel'))
            except Exception as e:
                db.session.rollback()
                flash(f"Erro ao salvar: {str(e)}", "danger")

        return render_template('chefe/registrar.html', horario=horario, alunos=alunos_turma, data_hoje=date.today())
    except Exception as e:
        flash(f"Erro: {str(e)}", "danger")
        return redirect(url_for('chefe.painel'))