# backend/controllers/relatorios_controller.py

from flask import Blueprint, render_template, request, flash, Response, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime
from urllib.parse import quote
# O import de 'locale' não é mais necessário para esta função
# import locale

from weasyprint import HTML

from ..services.relatorio_service import RelatorioService
from ..services.instrutor_service import InstrutorService
from ..services.site_config_service import SiteConfigService
from utils.decorators import admin_or_programmer_required

relatorios_bp = Blueprint('relatorios', __name__, url_prefix='/relatorios')


@relatorios_bp.route('/')
@login_required
@admin_or_programmer_required
def index():
    """Página que exibe os tipos de relatório disponíveis."""
    return render_template('relatorios/index.html')


@relatorios_bp.route('/gerar', methods=['GET', 'POST'])
@login_required
@admin_or_programmer_required
def gerar_relatorio_horas_aula():
    report_type = request.args.get('tipo', 'mensal')
    tipo_relatorio_titulo = report_type.replace("_", " ").title()

    todos_instrutores = []
    # Garante que a chamada de serviço só ocorra se necessário
    if report_type == 'por_instrutor':
        paginated_instrutores = InstrutorService.get_all_instrutores(current_user)
        if paginated_instrutores:
            todos_instrutores = paginated_instrutores.items

    if request.method == 'POST':
        data_inicio_str = request.form.get('data_inicio')
        data_fim_str = request.form.get('data_fim')
        action = request.form.get('action')

        try:
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            flash('Formato de data inválido. Use AAAA-MM-DD.', 'danger')
            return redirect(url_for('relatorios.gerar_relatorio_horas_aula', tipo=report_type))

        if data_fim < data_inicio:
            flash('A data de fim não pode ser anterior à data de início.', 'warning')
            return redirect(url_for('relatorios.gerar_relatorio_horas_aula', tipo=report_type))

        is_rr_filter = report_type == 'efetivo_rr'
        instrutor_ids_filter = None
        if report_type == 'por_instrutor':
            instrutor_ids_filter = [int(id) for id in request.form.getlist('instrutor_ids')]
            if not instrutor_ids_filter:
                flash('Por favor, selecione pelo menos um instrutor.', 'warning')
                return redirect(url_for('relatorios.gerar_relatorio_horas_aula', tipo=report_type))

        dados_relatorio = RelatorioService.get_horas_aula_por_instrutor(
            data_inicio, data_fim, is_rr_filter, instrutor_ids_filter
        )

        valor_hora_aula = SiteConfigService.get_valor_hora_aula()
        
        # --- LÓGICA DE TRADUÇÃO DO MÊS ---
        meses = ("Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro")
        nome_mes_ano_pt = f"{meses[data_inicio.month - 1]} de {data_inicio.year}"
        data_assinatura_pt = f"{data_fim.day} de {meses[data_fim.month - 1]} de {data_fim.year}"
        
        contexto = {
            "dados": dados_relatorio,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
            "titulo_curso": request.form.get('curso_nome'),
            "nome_mes_ano": nome_mes_ano_pt,
            "data_assinatura": data_assinatura_pt,
            "comandante_nome": request.form.get('comandante_nome'),
            "auxiliar_nome": request.form.get('auxiliar_nome'),
            "valor_hora_aula": valor_hora_aula,
            "opm": request.form.get('opm'),
            "telefone": request.form.get('telefone'),
            "cidade": request.form.get('cidade'),
            "auxiliar_funcao": request.form.get('auxiliar_funcao'),
            "comandante_funcao": request.form.get('comandante_funcao'),
        }

        if action == 'preview':
            rendered_html = render_template('relatorios/pdf_template.html', **contexto)
            return rendered_html
        
        elif action == 'download':
            rendered_html = render_template('relatorios/pdf_template.html', **contexto)
            try:
                pdf_content = HTML(string=rendered_html, base_url=request.url_root).write_pdf()
            except Exception as e:
                flash(f'Erro ao gerar PDF: {str(e)}', 'danger')
                return redirect(url_for('relatorios.gerar_relatorio_horas_aula', tipo=report_type))

            filename_utf8 = f'relatorio_horas_aula_{contexto["nome_mes_ano"].replace(" ", "_")}.pdf'
            return Response(
                pdf_content,
                mimetype='application/pdf',
                headers={'Content-Disposition': f'attachment; filename="{quote(filename_utf8)}'}
            )

        flash('Ação inválida.', 'warning')
        return redirect(url_for('relatorios.gerar_relatorio_horas_aula', tipo=report_type))

    return render_template(
        'relatorios/horas_aula_form.html',
        tipo_relatorio=tipo_relatorio_titulo,
        todos_instrutores=todos_instrutores
    )