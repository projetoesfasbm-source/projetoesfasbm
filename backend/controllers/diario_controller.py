# backend/controllers/diario_controller.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from ..services.diario_service import DiarioService
from ..services.user_service import UserService
# Importe um decorator apropriado se tiver, por enquanto usaremos login_required
# Sugestão: criar um decorator 'instrutor_required' futuramente

diario_bp = Blueprint('diario', __name__, url_prefix='/diario-classe')

@diario_bp.route('/instrutor/pendentes')
@login_required
def listar_pendentes():
    """Lista diários preenchidos por alunos aguardando validação do instrutor"""
    # Verifica se é instrutor (simples verificação de role ou se tem perfil de instrutor)
    # Aqui assumimos que o Service cuida da validação se o user tem perfil de instrutor
    
    diarios = DiarioService.get_diarios_pendentes_instrutor(current_user.id)
    
    return render_template('diario/instrutor_listar.html', diarios=diarios)

@diario_bp.route('/instrutor/assinar/<int:diario_id>', methods=['GET', 'POST'])
@login_required
def assinar(diario_id):
    """Tela de conferência e assinatura"""
    diario = DiarioService.get_diario_para_assinatura(diario_id, current_user.id)
    
    if not diario:
        flash("Diário não encontrado ou você não é o instrutor responsável.", "danger")
        return redirect(url_for('diario.listar_pendentes'))

    if request.method == 'POST':
        tipo = request.form.get('tipo_assinatura') # 'canvas' ou 'upload'
        
        if tipo == 'canvas':
            dados = request.form.get('assinatura_base64')
            if not dados:
                flash("Desenhe sua assinatura antes de salvar.", "warning")
                return render_template('diario/instrutor_assinar.html', diario=diario)
        elif tipo == 'upload':
            if 'assinatura_upload' not in request.files:
                flash("Nenhum arquivo selecionado.", "warning")
                return render_template('diario/instrutor_assinar.html', diario=diario)
            dados = request.files['assinatura_upload']
            if dados.filename == '':
                flash("Nenhum arquivo selecionado.", "warning")
                return render_template('diario/instrutor_assinar.html', diario=diario)
        else:
            flash("Método de assinatura inválido.", "danger")
            return render_template('diario/instrutor_assinar.html', diario=diario)

        sucesso, msg = DiarioService.assinar_diario(diario.id, current_user.id, tipo, dados)
        
        if sucesso:
            flash(msg, "success")
            return redirect(url_for('diario.listar_pendentes'))
        else:
            flash(msg, "danger")

    return render_template('diario/instrutor_assinar.html', diario=diario)