from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from backend.services.diario_service import DiarioService
from backend.services.turma_service import TurmaService
from backend.services.relatorio_service import RelatorioService
from utils.decorators import admin_required
from datetime import datetime
import io

diario_bp = Blueprint('diario', __name__)

@diario_bp.route('/diario/instrutor')
@login_required
def instrutor_listar():
    diarios = DiarioService.get_diarios_by_instrutor(current_user.id)
    return render_template('diario/instrutor_listar.html', diarios=diarios)

@diario_bp.route('/diario/assinar/<int:diario_id>', methods=['GET', 'POST'])
@login_required
def instrutor_assinar(diario_id):
    diario = DiarioService.get_diario_by_id(diario_id)
    if not diario or diario.instrutor_id != current_user.id:
        flash('Diário não encontrado ou acesso negado.', 'danger')
        return redirect(url_for('diario.instrutor_listar'))

    if request.method == 'POST':
        assinatura_data = request.form.get('assinatura_data')
        frequencias = []
        
        for key, value in request.form.items():
            if key.startswith('presenca_'):
                aluno_id = int(key.split('_')[1])
                frequencias.append({
                    'aluno_id': aluno_id,
                    'status': value
                })
        
        if DiarioService.assinar_diario(diario_id, assinatura_data, frequencias):
            flash('Diário assinado com sucesso!', 'success')
            return redirect(url_for('diario.instrutor_listar'))
        else:
            flash('Erro ao assinar diário.', 'danger')

    alunos = DiarioService.get_alunos_by_turma(diario.turma_id)
    return render_template('diario/instrutor_assinar.html', diario=diario, alunos=alunos)

@diario_bp.route('/admin/faltas')
@login_required
@admin_required
def admin_faltas():
    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')
    turma_id = request.args.get('turma_id', type=int)
    export_pdf = request.args.get('export_pdf') == 'true'

    hoje = datetime.now().date()
    
    if data_inicio_str:
        try:
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
        except ValueError:
            data_inicio = hoje
    else:
        data_inicio = hoje

    if data_fim_str:
        try:
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
        except ValueError:
            data_fim = hoje
    else:
        data_fim = hoje

    faltas = DiarioService.get_faltas_report(
        school_id=current_user.school_id,
        data_inicio=data_inicio,
        data_fim=data_fim,
        turma_id=turma_id
    )

    if export_pdf:
        pdf_data = RelatorioService.gerar_pdf_faltas(faltas, data_inicio, data_fim)
        return send_file(
            io.BytesIO(pdf_data),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"relatorio_faltas_{data_inicio}_a_{data_fim}.pdf"
        )

    turmas = TurmaService.get_turmas_by_school(current_user.school_id)
    return render_template('diario/admin_faltas.html', 
                           faltas=faltas, 
                           turmas=turmas, 
                           data_inicio=data_inicio, 
                           data_fim=data_fim, 
                           turma_id_sel=turma_id)