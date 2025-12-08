# backend/controllers/chefe_turma_controller.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, g
from flask_login import login_required, current_user
from datetime import date
from sqlalchemy import func

from backend.models.database import db
from backend.models.horario import Horario
from backend.models.aluno import Aluno
from backend.models.turma_cargo import TurmaCargo
from backend.models.diario_classe import DiarioClasse
from backend.models.frequencia import FrequenciaAluno
from backend.models.semana import Semana

chefe_bp = Blueprint('chefe', __name__, url_prefix='/chefe')

def verify_chefe_permission():
    """
    Verifica se o usuário atual é aluno e possui cargo de 'Chefe' na sua turma.
    Retorna o objeto Aluno se autorizado, ou None se negado.
    """
    if not current_user.is_authenticated or not current_user.aluno_profile:
        return None
    
    aluno = current_user.aluno_profile
    
    # Busca cargo na tabela TurmaCargo
    # Usamos ilike para garantir que 'Chefe', 'chefe', 'Chefe de Turma' sejam aceitos
    cargo = db.session.query(TurmaCargo).filter(
        TurmaCargo.aluno_id == aluno.id,
        TurmaCargo.cargo.ilike('%Chefe%')
    ).first()
    
    if cargo:
        return aluno
    return None

@chefe_bp.route('/painel')
@login_required
def painel():
    aluno = verify_chefe_permission()
    if not aluno:
        flash("Acesso restrito a Chefes de Turma.", "danger")
        return redirect(url_for('main.index'))

    # Identificar o dia da semana atual
    hoje = date.today()
    dia_semana_map = {0: 'Segunda', 1: 'Terça', 2: 'Quarta', 3: 'Quinta', 4: 'Sexta', 5: 'Sábado', 6: 'Domingo'}
    dia_str = dia_semana_map[hoje.weekday()]
    
    # Busca aulas do dia para a turma do chefe
    # (Idealmente deve cruzar com a Semana ativa, aqui pegamos pelo dia da semana genérico para simplificar,
    #  mas filtrando pela escola ativa se necessário)
    aulas_hoje = db.session.query(Horario).filter_by(
        turma_id=aluno.turma_id,
        dia_da_semana=dia_str
    ).order_by(Horario.hora_inicio).all()

    # Verificar quais aulas já tiveram chamada realizada hoje
    diarios_preenchidos = db.session.query(DiarioClasse).filter_by(
        data_aula=hoje, 
        turma_id=aluno.turma_id
    ).all()
    
    ids_disciplinas_feitas = [d.disciplina_id for d in diarios_preenchidos]

    return render_template('chefe/painel.html', 
                           aluno=aluno, 
                           aulas=aulas_hoje, 
                           feitos=ids_disciplinas_feitas,
                           data_hoje=hoje)

@chefe_bp.route('/registrar/<int:horario_id>', methods=['GET', 'POST'])
@login_required
def registrar_aula(horario_id):
    aluno_chefe = verify_chefe_permission()
    if not aluno_chefe:
        flash("Permissão negada.", "danger")
        return redirect(url_for('main.index'))

    horario = db.session.get(Horario, horario_id)
    
    # Segurança: Verificar se o horário pertence à turma do chefe
    if not horario or horario.turma_id != aluno_chefe.turma_id:
        flash("Horário inválido ou de outra turma.", "danger")
        return redirect(url_for('chefe.painel'))
        
    # Verificar se já foi feito hoje (evitar duplicidade)
    ja_feito = db.session.query(DiarioClasse).filter_by(
        data_aula=date.today(),
        turma_id=aluno_chefe.turma_id,
        disciplina_id=horario.disciplina_id
    ).first()
    
    if ja_feito:
        flash("A chamada para esta disciplina já foi realizada hoje.", "warning")
        return redirect(url_for('chefe.painel'))

    # Puxar alunos da turma (ordem alfabética ou numérica)
    alunos_turma = db.session.query(Aluno).filter_by(turma_id=aluno_chefe.turma_id).order_by(Aluno.num_aluno).all()

    if request.method == 'POST':
        observacoes = request.form.get('observacoes')
        conteudo = request.form.get('conteudo')
        
        try:
            # 1. Criar o Cabeçalho (Diario)
            novo_diario = DiarioClasse(
                data_aula=date.today(),
                turma_id=aluno_chefe.turma_id,
                disciplina_id=horario.disciplina_id,
                responsavel_id=current_user.id,
                observacoes=observacoes,
                conteudo_ministrado=conteudo
            )
            db.session.add(novo_diario)
            db.session.flush() # Garante que novo_diario.id seja gerado

            # 2. Criar as frequências individuais
            for aluno in alunos_turma:
                # Checkbox marcado = 'on' (Presente)
                # Checkbox desmarcado = None (Falta)
                presente = request.form.get(f'presenca_{aluno.id}') == 'on'
                
                freq = FrequenciaAluno(
                    diario_id=novo_diario.id,
                    aluno_id=aluno.id,
                    presente=presente
                )
                db.session.add(freq)
            
            db.session.commit()
            flash("Chamada e observações registradas com sucesso!", "success")
            return redirect(url_for('chefe.painel'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar: {str(e)}", "danger")

    return render_template('chefe/registrar.html', horario=horario, alunos=alunos_turma, data_hoje=date.today())