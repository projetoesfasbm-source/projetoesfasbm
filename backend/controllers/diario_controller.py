# backend/controllers/diario_controller.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
import os

from ..services.diario_service import DiarioService
from ..services.user_service import UserService
from utils.image_utils import compress_image_to_memory, allowed_file

diario_bp = Blueprint('diario', __name__, url_prefix='/diario-classe')

@diario_bp.route('/instrutor/pendentes')
@login_required
def listar_pendentes():
    school_id = UserService.get_current_school_id()
    if not school_id:
        flash("Escola não selecionada.", "warning")
        return redirect(url_for('main.dashboard'))

    status = request.args.get('status', 'pendente')
    turma_id = request.args.get('turma_id', type=int)
    disciplina_id = request.args.get('disciplina_id', type=int)
    
    diarios_agrupados = DiarioService.get_diarios_agrupados(
        school_id=school_id,
        user_id=current_user.id, 
        turma_id=turma_id,
        disciplina_id=disciplina_id,
        status=status
    )
    
    turmas, disciplinas = DiarioService.get_filtros_disponiveis(school_id, current_user.id, turma_id)
    
    return render_template('diario/instrutor_listar.html', 
                           diarios=diarios_agrupados, 
                           turmas=turmas,
                           disciplinas=disciplinas,
                           sel_status=status,
                           sel_turma=turma_id,
                           sel_disciplina=disciplina_id)

@diario_bp.route('/instrutor/assinar/<int:diario_id>', methods=['GET', 'POST'])
@login_required
def assinar(diario_id):
    diario, instrutor = DiarioService.get_diario_para_assinatura(diario_id, current_user.id)
    
    if not diario:
        flash("Diário não encontrado.", "danger")
        return redirect(url_for('diario.listar_pendentes'))

    if request.method == 'POST':
        tipo = request.form.get('tipo_assinatura')
        salvar = request.form.get('salvar_padrao') == 'on'
        
        conteudo_ministrado = request.form.get('conteudo_ministrado')
        observacoes = request.form.get('observacoes')
        
        dados = None

        if tipo == 'canvas': 
            dados = request.form.get('assinatura_base64')
        elif tipo == 'upload': 
            arquivo = request.files.get('assinatura_upload')
            
            # --- Lógica de Compressão para Assinatura ---
            if arquivo:
                if allowed_file(arquivo.filename, arquivo.stream, ['png', 'jpg', 'jpeg']):
                    # Comprime: 256x256, Qualidade 60
                    dados = compress_image_to_memory(arquivo, max_size=(256, 256), quality=60)
                    if not dados:
                        flash("Erro ao processar imagem da assinatura.", "danger")
                        return redirect(url_for('diario.listar_pendentes'))
                else:
                    flash("Formato de arquivo inválido para assinatura.", "danger")
                    return redirect(url_for('diario.listar_pendentes'))
            # ----------------------------------------------

        elif tipo == 'padrao': 
            dados = True

        ok, msg = DiarioService.assinar_diario(
            diario_id=diario.id, 
            user_id=current_user.id, 
            tipo_assinatura=tipo, 
            dados_assinatura=dados, 
            salvar_padrao=salvar,
            conteudo_atualizado=conteudo_ministrado,
            observacoes_atualizadas=observacoes
        )
        
        if ok:
            flash(msg, "success")
            return redirect(url_for('diario.listar_pendentes', status='assinado'))
        else:
            flash(msg, "danger")

    return render_template('diario/instrutor_assinar.html', diario=diario, instrutor=instrutor)