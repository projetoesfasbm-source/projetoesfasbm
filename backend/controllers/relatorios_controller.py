# backend/controllers/relatorios_controller.py

from __future__ import annotations
from datetime import date, datetime
from io import BytesIO
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request, send_file

from backend.services.xlsx_service import gerar_mapa_gratificacao_xlsx

# (Opcional) utilitários de diagnóstico; cai para fallback se não existir
try:
    from backend.utils.diagnostics import log_exception, scan_dataset_for_illegal_chars
except Exception:  # pragma: no cover
    def log_exception(context: Dict[str, Any], exc: BaseException) -> str:
        print("[relatorios_controller] EXCEPTION:", type(exc).__name__, str(exc))
        return "no-log-id"

    def scan_dataset_for_illegal_chars(dados: Any) -> Dict[str, Any]:
        return {"total_fields_checked": 0, "hits_count": 0, "hits": []}


relatorios_bp = Blueprint("relatorios", __name__, url_prefix="/relatorios")

@relatorios_bp.get("/")
def index():
    # Página simples com link para o XLSX
    from flask import url_for
    link = url_for("relatorios.mapa_gratificacao_xlsx")
    html = f"""<!doctype html>
<html lang="pt-br">
<head><meta charset="utf-8"><title>Relatórios</title></head>
<body style="font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; padding: 24px;">
  <h1>Relatórios</h1>
  <p>Use o link abaixo para gerar/baixar o mapa em XLSX.</p>
  <p><a href="{link}">Baixar Mapa de Gratificação (XLSX)</a></p>
</body>
</html>"""
    return html




# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _as_date_or_none(value: str | None) -> date | None:
    """Converte 'YYYY-MM-DD' em date. Retorna None se vazio/ inválido."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return None


def _coletar_dados_mapa() -> List[Dict[str, Any]]:
    """
    TODO: substitua por sua coleta real (banco/serviços).
    Estrutura esperada pelo gerar_mapa_gratificacao_xlsx():
    [
      {
        "info": {"user": {"posto_graduacao": "...", "matricula": "...", "nome_completo": "..."}},
        "disciplinas": [
            {"nome": "...", "ch_total": 0, "ch_paga_anteriormente": 0, "ch_a_pagar": 0},
            ...
        ],
      },
      ...
    ]
    """
    # Exemplo mínimo para não quebrar:
    return [
        {
            "info": {"user": {"posto_graduacao": "Sd PM", "matricula": "123456-7", "nome_completo": "Instrutor Exemplo"}},
            "disciplinas": [
                {"nome": "História", "ch_total": 12, "ch_paga_anteriormente": 0, "ch_a_pagar": 12},
            ],
        }
    ]


# ---------------------------------------------------------------------------
# XLSX via GET (não exige CSRF). Parâmetros via query string:
#   valor_hora_aula (float)
#   nome_mes_ano (str)
#   titulo_curso (str)
#   opm_nome (str)
#   escola_nome (str)
#   telefone (str)
#   auxiliar_nome (str)
#   comandante_nome (str)
#   digitador_nome (str)
#   auxiliar_funcao (str)
#   comandante_funcao (str)
#   data_emissao (YYYY-MM-DD)  [default: hoje]
#   data_fim (YYYY-MM-DD)
#   cidade_assinatura (str)
# ---------------------------------------------------------------------------
@relatorios_bp.get("/mapa-gratificacao.xlsx")
def mapa_gratificacao_xlsx():
    try:
        # ---- Parâmetros com defaults seguros ----
        valor_hora_aula = request.args.get("valor_hora_aula", type=float) or 0.0
        nome_mes_ano = request.args.get("nome_mes_ano", default=datetime.now().strftime("%B de %Y").title())
        titulo_curso = request.args.get("titulo_curso", default="Curso Técnico de Segurança Pública (CTSP)")
        opm_nome = request.args.get("opm_nome", default="Brigada Militar do RS")
        escola_nome = request.args.get("escola_nome", default="EsFAS")
        telefone = request.args.get("telefone", default=None)
        auxiliar_nome = request.args.get("auxiliar_nome", default=None)
        comandante_nome = request.args.get("comandante_nome", default=None)
        digitador_nome = request.args.get("digitador_nome", default=None)
        auxiliar_funcao = request.args.get("auxiliar_funcao", default="Auxiliar da Seção de Ensino")
        comandante_funcao = request.args.get("comandante_funcao", default="Comandante da EsFAS")
        cidade_assinatura = request.args.get("cidade_assinatura", default="Santa Maria")

        data_emissao = _as_date_or_none(request.args.get("data_emissao")) or date.today()
        data_fim = _as_date_or_none(request.args.get("data_fim"))

        # ---- Coleta dos dados (substitua pela sua implementação) ----
        dados = _coletar_dados_mapa()

        # (Opcional) diagnóstico de caracteres ilegais no dataset
        rep = scan_dataset_for_illegal_chars(dados)
        if rep.get("hits_count"):
            print(f"[DIAG] Caracteres ilegais detectados no dataset: {rep['hits_count']}")

        # ---- Geração do XLSX ----
        content = gerar_mapa_gratificacao_xlsx(
            dados=dados,
            valor_hora_aula=valor_hora_aula,
            nome_mes_ano=nome_mes_ano,
            titulo_curso=titulo_curso,
            opm_nome=opm_nome,
            escola_nome=escola_nome,
            data_emissao=data_emissao,
            telefone=telefone,
            auxiliar_nome=auxiliar_nome,
            comandante_nome=comandante_nome,
            digitador_nome=digitador_nome,
            auxiliar_funcao=auxiliar_funcao,
            comandante_funcao=comandante_funcao,
            data_fim=data_fim,
            cidade_assinatura=cidade_assinatura,
        )

        filename = f"Mapa_Gratificacao_{datetime.now():%Y_%m}.xlsx"
        return send_file(
            BytesIO(content),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )

    except Exception as e:
        err_id = log_exception(
            context={"route": "/relatorios/mapa-gratificacao.xlsx", "hint": "Falha ao gerar XLSX"},
            exc=e,
        )
        return jsonify({
            "ok": False,
            "error_id": err_id,
            "message": "Falha ao gerar planilha. Informe este código ao suporte.",
        }), 500
