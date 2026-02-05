# backend/controllers/diario_controller.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file, session
from flask_login import login_required, current_user
import os
from io import BytesIO
from datetime import datetime
from weasyprint import HTML

from ..services.diario_service import DiarioService
from ..services.user_service import UserService
from ..services.turma_service import TurmaService
from ..services.school_service import SchoolService
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
            if arquivo:
                if allowed_file(arquivo.filename, arquivo.stream, ['png', 'jpg', 'jpeg']):
                    dados = compress_image_to_memory(arquivo, max_size=(256, 256), quality=60)
                    if not dados:
                        flash("Erro ao processar imagem da assinatura.", "danger")
                        return redirect(url_for('diario.listar_pendentes'))
                else:
                    flash("Formato de arquivo inválido para assinatura.", "danger")
                    return redirect(url_for('diario.listar_pendentes'))

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

@diario_bp.route('/admin/faltas', methods=['GET'])
@login_required
def admin_faltas():
    """
    Rota administrativa para busca e exportação de faltas.
    Acesso restrito a usuários com papel SENS (Secretaria de Ensino) ou Programadores.
    """
    active_sid = session.get('active_school_id')
    if not active_sid:
        flash("Nenhuma escola ativa selecionada.", "warning")
        return redirect(url_for('main.dashboard'))
    
    # Validação de permissão padrão do seu sistema
    if not (current_user.is_sens_in_school(active_sid) or current_user.is_programador):
        flash("Acesso negado. Você não possui permissão para ver este relatório.", "danger")
        return redirect(url_for('main.dashboard'))
    
    school_id = int(active_sid)
    turmas = TurmaService.get_turmas_by_school(school_id)
    
    data_ini_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')
    turma_id = request.args.get('turma_id', type=int)
    exportar = request.args.get('exportar')

    faltas = []
    if data_ini_str and data_fim_str:
        try:
            d1 = datetime.strptime(data_ini_str, '%Y-%m-%d').date()
            d2 = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
            
            faltas_data = DiarioService.get_faltas_report_data(school_id, d1, d2, turma_id)

            if exportar == 'pdf':
                escola = SchoolService.get_school_by_id(school_id)
                html = render_template('diario/pdf_faltas.html', 
                                       faltas=faltas_data, 
                                       escola=escola, 
                                       d1=d1.strftime('%d/%m/%Y'), 
                                       d2=d2.strftime('%d/%m/%Y'),
                                       agora=datetime.now())
                
                pdf = HTML(string=html).write_pdf()
                return send_file(
                    BytesIO(pdf),
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f"Relatorio_Faltas_{data_ini_str}_a_{data_fim_str}.pdf"
                )
            
            faltas = faltas_data
        except Exception as e:
            flash(f"Erro ao processar busca: {str(e)}", "danger")

    return render_template(
        'diario/admin_faltas.html', 
        turmas=turmas, 
        faltas=faltas, 
        params=request.args
    )