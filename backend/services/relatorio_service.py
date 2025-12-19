# backend/services/relatorio_service.py

from __future__ import annotations
import os
import json
from io import BytesIO
from typing import Any, Dict, List, Tuple
from datetime import date
from sqlalchemy import func, select, union_all

# Importações seguras que não dependem do banco de dados ou de outros serviços locais
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
GA_CREDENTIALS_JSON = os.environ.get("GA_CREDENTIALS_JSON")

def _get_google_credentials() -> Credentials:
    if not GA_CREDENTIALS_JSON:
        raise RuntimeError("A variável de ambiente GA_CREDENTIALS_JSON não foi configurada.")
    try:
        info = json.loads(GA_CREDENTIALS_JSON)
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    except Exception as e:
        raise RuntimeError(f"Erro ao carregar credenciais do Google: {e}")

def _upload_xlsx_and_convert_to_sheet(filename: str, xlsx_bytes: bytes) -> str | None:
    try:
        creds = _get_google_credentials()
        service = build('drive', 'v3', credentials=creds)
        file_metadata = {'name': filename, 'mimeType': 'application/vnd.google-apps.spreadsheet'}
        media = MediaIoBaseUpload(BytesIO(xlsx_bytes), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
        permission = {'type': 'anyone', 'role': 'reader'}
        service.permissions().create(fileId=file.get('id'), body=permission).execute()
        return file.get('webViewLink')
    except HttpError as error:
        print(f"Ocorreu um erro na API do Google Drive: {error}")
        return None
    except Exception as e:
        print(f"Ocorreu um erro inesperado durante o upload para o Google Drive: {e}")
        return None

class RelatorioService:

    @staticmethod
    def get_horas_aula_por_instrutor(
        data_inicio: date,
        data_fim: date,
        is_rr_filter: bool,
        instrutor_ids_filter: List[int] | None
    ) -> List[Dict[str, Any]]:
        """
        Busca e formata os dados de horas-aula por instrutor, corrigindo a consulta
        para usar as colunas corretas e somar horas de instrutores primários e secundários.
        """
        # As importações são feitas DENTRO da função para garantir que o contexto do app Flask esteja pronto.
        from ..models import db, Horario, User, Instrutor, Disciplina, Semana

        # Subquery para "desnormalizar" os instrutores, tratando instrutor_id e instrutor_id_2 como linhas separadas.
        # Isso simplifica a agregação e garante que ambos sejam contabilizados.
        s1 = select(Horario.instrutor_id.label("instrutor_id"), Horario.duracao, Horario.disciplina_id, Horario.semana_id).where(Horario.instrutor_id.isnot(None))
        s2 = select(Horario.instrutor_id_2.label("instrutor_id"), Horario.duracao, Horario.disciplina_id, Horario.semana_id).where(Horario.instrutor_id_2.isnot(None))
        unioned_horarios = union_all(s1, s2).alias("unioned_horarios")

        # Query principal que agora utiliza a subquery.
        query = (
            select(
                User.posto_graduacao,
                User.matricula,
                User.nome_completo,
                Disciplina.materia.label('disciplina_nome'),
                func.sum(unioned_horarios.c.duracao).label('ch_a_pagar'),
                Disciplina.carga_horaria_prevista.label('ch_total')
            )
            .select_from(User)
            .join(Instrutor, User.id == Instrutor.user_id)
            .join(unioned_horarios, Instrutor.id == unioned_horarios.c.instrutor_id)
            .join(Disciplina, unioned_horarios.c.disciplina_id == Disciplina.id)
            .join(Semana, unioned_horarios.c.semana_id == Semana.id)
            .filter(
                Semana.data_inicio <= data_fim,
                Semana.data_fim >= data_inicio
            )
            .group_by(
                User.posto_graduacao, User.matricula, User.nome_completo,
                Disciplina.materia, Disciplina.carga_horaria_prevista
            )
            .order_by(User.matricula.asc())  # Alterado de nome_completo para matricula.asc()
        )

        # Aplica filtros opcionais de forma correta
        if is_rr_filter:
            query = query.where(Instrutor.is_rr == True)
        if instrutor_ids_filter:
            query = query.where(Instrutor.id.in_(instrutor_ids_filter))

        # Executa a query e obtém os resultados como dicionários
        resultados_db = db.session.execute(query).mappings().all()
        
        # Agrupa os resultados em Python (lógica mantida, pois está correta)
        dados_agrupados = {}
        for r in resultados_db:
            matricula = r['matricula'] or r['nome_completo']
            if matricula not in dados_agrupados:
                dados_agrupados[matricula] = {
                    "info": {"user": {
                        "posto_graduacao": r['posto_graduacao'], "matricula": r['matricula'], "nome_completo": r['nome_completo'],
                    }},
                    "disciplinas": []
                }
            dados_agrupados[matricula]["disciplinas"].append({
                "nome": r['disciplina_nome'], "ch_total": r['ch_total'] or 0,
                "ch_paga_anteriormente": 0,  # Este campo pode ser calculado no futuro se necessário
                "ch_a_pagar": r['ch_a_pagar'] or 0,
            })
        return list(dados_agrupados.values())

    @staticmethod
    def export_to_google_sheets(contexto: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Gera o arquivo XLSX em memória e faz o upload para o Google Drive.
        """
        # Importa o gerador de XLSX aqui dentro para evitar erros de importação na inicialização.
        from .xlsx_service import gerar_mapa_gratificacao_xlsx
        
        try:
            xlsx_bytes = gerar_mapa_gratificacao_xlsx(
                dados=contexto.get("dados"),
                valor_hora_aula=float(contexto.get("valor_hora_aula") or 0.0),
                nome_mes_ano=contexto.get("nome_mes_ano"),
                titulo_curso=contexto.get("titulo_curso"),
                opm_nome=contexto.get("opm"),
                escola_nome=contexto.get("escola_nome"),
                data_emissao=contexto.get("data_emissao"),
                telefone=contexto.get("telefone"),
                auxiliar_nome=contexto.get("auxiliar_nome"),
                comandante_nome=contexto.get("comandante_nome"),
                digitador_nome=contexto.get("digitador_nome"),
                auxiliar_funcao=contexto.get("auxiliar_funcao"),
                comandante_funcao=contexto.get("comandante_funcao"),
                data_fim=contexto.get("data_fim"),
                cidade_assinatura=contexto.get("cidade"),
            )

            nome_arquivo = f'Relatório Horas-Aula - {contexto.get("nome_mes_ano", "geral")}'
            sheet_url = _upload_xlsx_and_convert_to_sheet(nome_arquivo, xlsx_bytes)
            
            if sheet_url:
                return True, sheet_url
            else:
                return False, "Falha no upload do arquivo para o Google Drive. Verifique as credenciais da API."
        except Exception as e:
            print(f"ERRO CRÍTICO ao exportar para Google Sheets: {e}")
            return False, f"Ocorreu um erro interno ao gerar ou enviar o arquivo: {e}"