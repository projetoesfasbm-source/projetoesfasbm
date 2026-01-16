# backend/controllers/diario_controller.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from ..services.diario_service import DiarioService

diario_bp = Blueprint('diario', __name__, url_prefix='/diario-classe')

@diario_bp.route('/instrutor/pendentes')
@login_required
def listar_pendentes():
    diarios = DiarioService.get_diarios_pendentes_instrutor(current_user.id)
    return render_template('diario/instrutor_listar.html', diarios=diarios)

@diario_bp.route('/instrutor/assinar/<int:diario_id>', methods=['GET', 'POST'])
@login_required
def assinar(diario_id):
    # Agora retorna tupla (diario, instrutor)
    diario, instrutor = DiarioService.get_diario_para_assinatura(diario_id, current_user.id)
    
    if not diario:
        flash("Diário não encontrado ou permissão negada.", "danger")
        return redirect(url_for('diario.listar_pendentes'))

    if request.method == 'POST':
        tipo = request.form.get('tipo_assinatura')
        salvar_padrao = request.form.get('salvar_padrao') == 'on'
        dados = None

        if tipo == 'canvas':
            dados = request.form.get('assinatura_base64')
        elif tipo == 'upload':
            dados = request.files.get('assinatura_upload')
        elif tipo == 'padrao':
            dados = True # Apenas flag para validação interna

        sucesso, msg = DiarioService.assinar_diario(
            diario.id, 
            current_user.id, 
            tipo, 
            dados, 
            salvar_padrao
        )
        
        if sucesso:
            flash(msg, "success")
            return redirect(url_for('diario.listar_pendentes'))
        else:
            flash(msg, "danger")

    return render_template('diario/instrutor_assinar.html', diario=diario, instrutor=instrutor)