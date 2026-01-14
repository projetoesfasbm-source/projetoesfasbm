from flask import Blueprint, render_template, request, flash, redirect, url_for, g
from flask_login import login_required
from ..models.database import db
from ..models.discipline_rule import DisciplineRule
from utils.decorators import admin_or_programmer_required

regras_bp = Blueprint('regras', __name__, url_prefix='/regras')

ATRIBUTOS_FADA = {
    1: 'Expressão', 2: 'Planejamento', 3: 'Perseverança', 4: 'Apresentação Pessoal',
    5: 'Lealdade', 6: 'Tato', 7: 'Equilíbrio Emocional', 8: 'Disciplina',
    9: 'Responsabilidade', 10: 'Maturidade', 11: 'Assiduidade', 12: 'Pontualidade',
    13: 'Dicção', 14: 'Liderança', 15: 'Relacionamento Interpessoal',
    16: 'Ética Profissional', 17: 'Produtividade', 18: 'Eficiência'
}

@regras_bp.route('/')
@login_required
@admin_or_programmer_required
def index():
    tipo = g.active_school.npccal_type or 'cbfpm'
    regras = DisciplineRule.query.filter_by(npccal_type=tipo).order_by(DisciplineRule.codigo).all()
    return render_template('regras/index.html', regras=regras, atributos=ATRIBUTOS_FADA)

@regras_bp.route('/nova', methods=['GET', 'POST'])
@login_required
@admin_or_programmer_required
def nova():
    if request.method == 'POST':
        try:
            nova_regra = DisciplineRule(
                npccal_type=request.form.get('npccal_type'),
                codigo=request.form.get('codigo'),
                descricao=request.form.get('descricao'),
                gravidade=request.form.get('gravidade'),
                pontos=float(request.form.get('pontos')),
                atributo_fada_id=int(request.form.get('atributo_fada_id') or 0) or None
            )
            db.session.add(nova_regra)
            db.session.commit()
            flash('Regra criada com sucesso!', 'success')
            return redirect(url_for('regras.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {e}', 'danger')

    return render_template('regras/editar.html', regra=None, atributos=ATRIBUTOS_FADA, tipo_padrao=g.active_school.npccal_type)

@regras_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_or_programmer_required
def editar(id):
    regra = db.session.get(DisciplineRule, id)
    if not regra:
        flash('Regra não encontrada', 'danger')
        return redirect(url_for('regras.index'))

    if request.method == 'POST':
        try:
            regra.codigo = request.form.get('codigo')
            regra.descricao = request.form.get('descricao')
            regra.gravidade = request.form.get('gravidade')
            regra.pontos = float(request.form.get('pontos'))
            
            attr_id = request.form.get('atributo_fada_id')
            regra.atributo_fada_id = int(attr_id) if attr_id else None
            
            db.session.commit()
            flash('Regra atualizada com sucesso!', 'success')
            return redirect(url_for('regras.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar: {e}', 'danger')

    return render_template('regras/editar.html', regra=regra, atributos=ATRIBUTOS_FADA)

@regras_bp.route('/excluir/<int:id>', methods=['POST'])
@login_required
@admin_or_programmer_required
def excluir(id):
    regra = db.session.get(DisciplineRule, id)
    if regra:
        db.session.delete(regra)
        db.session.commit()
        flash('Regra removida.', 'success')
    return redirect(url_for('regras.index'))