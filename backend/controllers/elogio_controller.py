from flask import Blueprint, render_template, request, flash, redirect, url_for, g
from flask_login import login_required, current_user
from datetime import datetime
from ..models.database import db
from ..models.aluno import Aluno
from ..models.elogio import Elogio
from ..services.aluno_service import AlunoService
from utils.decorators import admin_or_programmer_required

elogio_bp = Blueprint('elogio', __name__, url_prefix='/elogio')

ATRIBUTOS_FADA = [
    (1, 'Expressão'), (2, 'Planejamento'), (3, 'Perseverança'), (4, 'Apresentação Pessoal'),
    (5, 'Lealdade'), (6, 'Tato'), (7, 'Equilíbrio Emocional'), (8, 'Disciplina'),
    (9, 'Responsabilidade'), (10, 'Maturidade'), (11, 'Assiduidade'), (12, 'Pontualidade'),
    (13, 'Dicção'), (14, 'Liderança'), (15, 'Relacionamento Interpessoal'),
    (16, 'Ética Profissional'), (17, 'Produtividade'), (18, 'Eficiência')
]

@elogio_bp.route('/novo/<int:aluno_id>', methods=['GET', 'POST'])
@login_required
@admin_or_programmer_required
def novo_elogio(aluno_id):
    aluno = AlunoService.get_aluno_by_id(aluno_id)
    if not aluno:
        flash('Aluno não encontrado.', 'danger')
        return redirect(url_for('aluno.listar_alunos'))

    active_school = g.get('active_school')
    usa_fada = active_school and active_school.npccal_type in ['cbfpm', 'cspm']

    if request.method == 'POST':
        descricao = request.form.get('descricao')
        data_elogio_str = request.form.get('data_elogio')
        
        pontos = 0.0
        attr1 = None
        attr2 = None

        if usa_fada:
            try:
                raw_attr1 = request.form.get('atributo_1')
                raw_attr2 = request.form.get('atributo_2')
                attr1 = int(raw_attr1) if raw_attr1 else None
                attr2 = int(raw_attr2) if raw_attr2 else None
                if attr1 or attr2:
                    pontos = 0.5
            except ValueError:
                pass
        
        try:
            data_elogio = datetime.strptime(data_elogio_str, '%Y-%m-%d').date()
            novo = Elogio(
                aluno_id=aluno.id,
                registrado_por_id=current_user.id,
                data_elogio=data_elogio,
                descricao=descricao,
                pontos=pontos,
                atributo_1=attr1,
                atributo_2=attr2
            )
            db.session.add(novo)
            db.session.commit()
            
            msg = 'Elogio registrado com sucesso!'
            if pontos > 0:
                msg += f' (+{pontos} pontos computados para FADA)'
            
            flash(msg, 'success')
            return redirect(url_for('aluno.editar_aluno', aluno_id=aluno.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao salvar elogio: {str(e)}', 'danger')

    return render_template(
        'elogios/novo.html', 
        aluno=aluno, 
        atributos=ATRIBUTOS_FADA,
        usa_fada=usa_fada,
        hoje=datetime.today().strftime('%Y-%m-%d')
    )

@elogio_bp.route('/deletar/<int:elogio_id>', methods=['POST'])
@login_required
@admin_or_programmer_required
def deletar_elogio(elogio_id):
    elogio = db.session.get(Elogio, elogio_id)
    if elogio:
        aluno_id = elogio.aluno_id
        db.session.delete(elogio)
        db.session.commit()
        flash('Elogio removido.', 'success')
        return redirect(url_for('aluno.editar_aluno', aluno_id=aluno_id))
    
    flash('Elogio não encontrado.', 'danger')
    return redirect(url_for('main.dashboard'))