# backend/controllers/relatorios_controller.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, send_file
from flask_login import login_required, current_user
from datetime import datetime
from typing import Optional
import io
import locale

from weasyprint import HTML
from werkzeug.utils import secure_filename

from ..services.relatorio_service import RelatorioService
from ..services.instrutor_service import InstrutorService
from ..services.site_config_service import SiteConfigService
from ..services.xlsx_service import gerar_mapa_gratificacao_xlsx
from ..services.user_service import UserService
from utils.decorators import admin_or_programmer_required

relatorios_bp = Blueprint('relatorios', _name_, url_prefix='/relatorios')


def _build_filename(prefix: str, label: Optional[str], extension: str, fallback: Optional[str] = None) -> str:
    label_component = label.strip() if isinstance(label, str) else None
    default_stub = fallback or prefix or "relatorio"
    base_name = "_".join(filter(None, (prefix, label_component))) or default_stub
    safe_with_ext = secure_filename(f"{base_name}.{extension}")
    if safe_with_ext:
        return safe_with_ext
    return secure_filename(f"{default_stub}.{extension}") or f"{default_stub}.{extension}"


@relatorios_bp.route('/')
@login_required
@admin_or_programmer_required
def index():
    return render_template('relatorios/index.html')


@relatorios_bp.route('/gerar', methods=['GET', 'POST'])
@login_required
@admin_or_programmer_required
def gerar_relatorio_horas_aula():
    school_id = UserService.get_current_school_id()
    if not school_id:
        flash('Nenhuma escola selecionada.', 'warning')
        return redirect(url_for('main.dashboard'))

    report_type = request.args.get('tipo', 'mensal')
    tipo_relatorio_titulo = report_type.replace("_", " ").title()

    todos_instrutores = []
    if report_type == 'por_instrutor':
        paginated_instrutores = InstrutorService.get_all_instrutores(current_user)
        if paginated_instrutores:
            todos_instrutores = paginated_instrutores.items

    report_defaults = {
        "curso_nome": "Curso Técnico em Segurança Pública",
        "opm": "Escola de Formação e Aperfeiçoamento de Sargentos",
        "escola_nome": "Escola de Formação e Aperfeiçoamento de Sargentos",
        "telefone": "(55) 3220-6462",
        "cidade": SiteConfigService.get_config('report_cidade_estado', 'Santa Maria - RS') or 'Santa Maria - RS',
        "comandante_funcao": SiteConfigService.get_config('report_comandante_cargo', 'Comandante da EsFAS-SM') or 'Comandante da EsFAS-SM',
        "auxiliar_funcao": SiteConfigService.get_config('report_chefe_ensino_cargo', 'Chefe da Seção de Ensino') or 'Chefe da Seção de Ensino',
    }

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
            instrutor_ids_raw = request.form.getlist('instrutor_ids')
            if not instrutor_ids_raw:
                flash('Por favor, selecione pelo menos um instrutor.', 'warning')
                return redirect(url_for('relatorios.gerar_relatorio_horas_aula', tipo=report_type))
            instrutor_ids_filter = [int(_id) for _id in instrutor_ids_raw if _id.isdigit()]
            if not instrutor_ids_filter:
                flash('Seleção de instrutores inválida.', 'warning')
                return redirect(url_for('relatorios.gerar_relatorio_horas_aula', tipo=report_type))

        # --- AQUI ESTA A CORREÇÃO: Passando school_id ---
        dados_relatorio = RelatorioService.get_horas_aula_por_instrutor(
            data_inicio, data_fim, is_rr_filter, instrutor_ids_filter, school_id
        )
        valor_hora_aula = SiteConfigService.get_valor_hora_aula()

        meses = ("Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                 "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro")
        nome_mes_ano_pt = f"{meses[data_inicio.month - 1]} de {data_inicio.year}"
        data_assinatura_pt = f"{data_fim.day} de {meses[data_fim.month - 1]} de {data_fim.year}"

        curso_nome = (request.form.get('curso_nome') or '').strip() or report_defaults["curso_nome"]
        opm_nome = (request.form.get('opm') or '').strip() or report_defaults["opm"]
        escola_nome = (request.form.get('escola_nome') or '').strip() or report_defaults["escola_nome"]
        telefone = (request.form.get('telefone') or '').strip() or report_defaults["telefone"]
        cidade = (request.form.get('cidade') or '').strip() or report_defaults["cidade"]
        comandante_funcao = (request.form.get('comandante_funcao') or '').strip() or report_defaults["comandante_funcao"]
        auxiliar_funcao = (request.form.get('auxiliar_funcao') or '').strip() or report_defaults["auxiliar_funcao"]

        contexto = {
            "dados": dados_relatorio, "data_inicio": data_inicio, "data_fim": data_fim, "titulo_curso": curso_nome,
            "nome_mes_ano": nome_mes_ano_pt, "data_assinatura": data_assinatura_pt,
            "comandante_nome": (request.form.get('comandante_nome') or '').strip(),
            "auxiliar_nome": (request.form.get('auxiliar_nome') or '').strip(),
            "valor_hora_aula": valor_hora_aula, "opm": opm_nome, "telefone": telefone, "cidade": cidade,
            "auxiliar_funcao": auxiliar_funcao, "comandante_funcao": comandante_funcao, "escola_nome": escola_nome,
        }

        if action == 'preview':
            return render_template('relatorios/pdf_template.html', **contexto)

        elif action == 'download':
            rendered_html = render_template('relatorios/pdf_template.html', **contexto)
            try:
                pdf_content = HTML(string=rendered_html, base_url=request.url_root).write_pdf()
            except Exception as e:
                flash(f'Erro ao gerar PDF: {str(e)}', 'danger')
                return redirect(url_for('relatorios.gerar_relatorio_horas_aula', tipo=report_type))
            pdf_name = _build_filename('relatorio_horas_aula', contexto.get("nome_mes_ano"), 'pdf')
            return send_file(io.BytesIO(pdf_content), as_attachment=True, download_name=pdf_name, mimetype='application/pdf')

        elif action == 'download_xlsx':
            try:
                xlsx_bytes = gerar_mapa_gratificacao_xlsx(
                    dados=dados_relatorio, valor_hora_aula=valor_hora_aula, nome_mes_ano=contexto["nome_mes_ano"],
                    titulo_curso=contexto.get("titulo_curso") or "", opm_nome=contexto.get("opm") or "",
                    escola_nome=contexto.get("escola_nome") or escola_nome, data_emissao=data_fim, telefone=contexto.get("telefone"),
                    auxiliar_nome=contexto.get("auxiliar_nome"), comandante_nome=contexto.get("comandante_nome"),
                    digitador_nome=(getattr(current_user, 'nome_completo', None) or getattr(current_user, 'username', None)),
                    auxiliar_funcao=contexto.get("auxiliar_funcao"), comandante_funcao=contexto.get("comandante_funcao"),
                    data_fim=data_fim, cidade_assinatura=contexto.get("cidade") or report_defaults["cidade"],
                )
            except Exception as e:
                flash(f'Erro ao gerar XLSX: {str(e)}', 'danger')
                return redirect(url_for('relatorios.gerar_relatorio_horas_aula', tipo=report_type))

            xlsx_name = _build_filename('relatorio_horas_aula', contexto.get("nome_mes_ano"), 'xlsx')
            return send_file(io.BytesIO(xlsx_bytes), as_attachment=True, download_name=xlsx_name, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        flash('Ação inválida.', 'warning')
        return redirect(url_for('relatorios.gerar_relatorio_horas_aula', tipo=report_type))

    return render_template(
        'relatorios/horas_aula_form.html',
        tipo_relatorio=tipo_relatorio_titulo,
        todos_instrutores=todos_instrutores,
        form_defaults=report_defaults,
    )