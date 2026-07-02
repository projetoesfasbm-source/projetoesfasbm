from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from datetime import datetime

from backend.models.database import db
from backend.models.aluno import Aluno
from backend.models.desligamento import RegistroDesligamento
from backend.services.user_service import UserService

# Importando a sua trava de segurança que já existe no sistema
from backend.controllers.admin_controller import sens_permission_required

desligamento_bp = Blueprint('desligamento', __name__, url_prefix='/desligamentos')

@desligamento_bp.route('/')
@login_required
@sens_permission_required
def index():
    """Tela principal listando todos os alunos desligados desta edição"""
    from backend.models.edicao import Edicao
    from backend.models.turma import Turma

    school_id = UserService.get_current_school_id()
    active_edicao = session.get('active_edicao_id')
    
    if not school_id or not active_edicao:
        flash("Selecione uma escola e uma edição para acessar os desligamentos.", "warning")
        return redirect(url_for('main.dashboard'))

    registros = db.session.query(RegistroDesligamento).filter(
        RegistroDesligamento.edicao_id == active_edicao
    ).order_by(RegistroDesligamento.data_desligamento.desc()).all()

    alunos_ativos = db.session.query(Aluno).filter(
        Aluno.edicao_id == active_edicao,
        Aluno.status_matricula == 'Ativo',
        Aluno.turma_id != None
    ).all()

    # --- NOVAS BUSCAS PARA O MODAL DE REVERSÃO ---
    todas_edicoes = db.session.query(Edicao).order_by(Edicao.id.desc()).all()
    todas_turmas = db.session.query(Turma).filter(Turma.school_id == school_id).order_by(Turma.nome).all()

    return render_template(
        'desligamento/index.html', 
        registros=registros, 
        alunos_ativos=alunos_ativos,
        todas_edicoes=todas_edicoes,
        todas_turmas=todas_turmas
    )


@desligamento_bp.route('/executar', methods=['POST'])
@login_required
@sens_permission_required
def executar_desligamento():
    """Lógica que efetivamente desliga o aluno e arquiva os dados"""
    aluno_id = request.form.get('aluno_id')
    motivo = request.form.get('motivo')
    observacoes = request.form.get('observacoes')
    active_edicao = session.get('active_edicao_id')

    aluno = db.session.get(Aluno, aluno_id)
    
    if not aluno:
        flash("Aluno não encontrado.", "danger")
        return redirect(url_for('desligamento.index'))

    try:
        # 1. Congela o aluno
        aluno.status_matricula = 'Desligado'
        
        # 2. Guarda de qual turma ele era para histórico, antes de remover
        turma_antiga = aluno.turma.nome if aluno.turma else "Sem Turma"
        
        # 3. Remove o vínculo da turma (Isso faz ele sumir das chamadas dos instrutores)
        aluno.turma_id = None 

        # 4. Cria a auditoria oficial do desligamento
        registro = RegistroDesligamento(
            aluno_id=aluno.id,
            admin_id=current_user.id,
            edicao_id=active_edicao,
            motivo=motivo,
            observacoes=f"[Turma Original: {turma_antiga}] {observacoes}" if observacoes else f"[Turma Original: {turma_antiga}]"
        )

        db.session.add(registro)
        db.session.commit()

        flash(f"O aluno {aluno.user.nome_de_guerra} foi desligado com sucesso.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao processar o desligamento: {str(e)}", "danger")

    return redirect(url_for('desligamento.index'))


@desligamento_bp.route('/dossie/<int:aluno_id>')
@login_required
@sens_permission_required
def dossie_aluno(aluno_id):
    """Tela de visualização Read-Only do histórico do aluno desligado"""
    aluno = db.session.get(Aluno, aluno_id)
    
    if not aluno or aluno.status_matricula != 'Desligado':
        flash("Dossiê inválido ou aluno ainda está ativo.", "danger")
        return redirect(url_for('desligamento.index'))
        
    registro = db.session.query(RegistroDesligamento).filter_by(aluno_id=aluno.id).order_by(RegistroDesligamento.id.desc()).first()

    # Passamos o aluno para a tela. Como usamos o SQLAlchemy, o Jinja2 conseguirá 
    # puxar aluno.frequencias, aluno.elogios, aluno.processos_disciplinares automaticamente!
    return render_template('desligamento/dossie.html', aluno=aluno, registro=registro)

@desligamento_bp.route('/reverter/<int:registro_id>', methods=['POST'])
@login_required
@sens_permission_required
def reverter_desligamento(registro_id):
    """Lógica para reativar o aluno, movendo-o para uma turma/edição e desbloqueando o acesso"""
    from backend.models.turma import Turma
    
    nova_edicao_id = request.form.get('nova_edicao_id', type=int)
    nova_turma_id = request.form.get('nova_turma_id', type=int)

    # Busca o registro de auditoria do desligamento
    registro = db.session.get(RegistroDesligamento, registro_id)
    if not registro:
        flash("Registro de desligamento não encontrado.", "danger")
        return redirect(url_for('desligamento.index'))

    aluno = registro.aluno
    if not aluno:
        flash("Aluno associado não encontrado.", "danger")
        return redirect(url_for('desligamento.index'))

    try:
        # 1. Atualiza os dados de matrícula do aluno para os novos selecionados
        aluno.status_matricula = 'Ativo'
        aluno.edicao_id = nova_edicao_id
        aluno.turma_id = nova_turma_id

        # 2. Atualiza a observação do registro para deixar documentado que foi revertido
        turma_destino = db.session.get(Turma, nova_turma_id)
        nome_turma = turma_destino.nome if turma_destino else "N/D"
        registro.observacoes = f"[REVERTIDO em {datetime.utcnow().strftime('%d/%m/%Y')} para Turma: {nome_turma}] -- " + (registro.observacoes or "")

        db.session.commit()
        flash(f"O aluno {aluno.user.nome_de_guerra} foi reativado com sucesso e o acesso foi desbloqueado!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao reverter o desligamento: {str(e)}", "danger")

    return redirect(url_for('desligamento.index'))
