# backend/controllers/diario_controller.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from ..services.diario_service import DiarioService
from ..services.user_service import UserService

diario_bp = Blueprint('diario', __name__, url_prefix='/diario-classe')

@diario_bp.route('/instrutor/pendentes')
@login_required
def listar_pendentes():
    school_id = UserService.get_current_school_id()
    if not school_id:
        flash("Escola não selecionada.", "warning")
        return redirect(url_for('main.dashboard'))

    # Filtros da URL
    turma_id = request.args.get('turma_id', type=int)
    disciplina_id = request.args.get('disciplina_id', type=int)
    
    # Determina o escopo: Admin vê tudo, Instrutor vê só o seu
    user_context_id = current_user.id
    is_admin = False
    
    # Se for Admin, SENS ou Programador, user_context_id vira None (para pegar tudo)
    if current_user.is_sens_in_school(school_id) or current_user.is_admin_escola_in_school(school_id) or current_user.is_programador:
        user_context_id = None
        is_admin = True

    # Busca Diários
    diarios = DiarioService.get_diarios_pendentes(
        school_id, 
        user_context_id, 
        turma_id, 
        disciplina_id
    )
    
    # Busca Listas para os Dropdowns (Turmas e Disciplinas)
    turmas_filtro, disciplinas_filtro = DiarioService.get_filtros_disponiveis(school_id, user_context_id)
    
    return render_template('diario/instrutor_listar.html', 
                           diarios=diarios, 
                           turmas=turmas_filtro,
                           disciplinas=disciplinas_filtro,
                           sel_turma=turma_id,
                           sel_disciplina=disciplina_id,
                           is_admin=is_admin)

@diario_bp.route('/instrutor/assinar/<int:diario_id>', methods=['GET', 'POST'])
@login_required
def assinar(diario_id):
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
            dados = True

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