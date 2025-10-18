# backend/services/relatorio_service.py

from __future__ import annotations
import os
import json
from io import BytesIO
from typing import Any, Dict, List, Tuple
from datetime import date

# As importações do Google são seguras para serem mantidas no topo
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError

# A importação do gerador de XLSX também é segura
from .xlsx_service import gerar_mapa_gratificacao_xlsx


# --- Funções Auxiliares para o Google Drive ---

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
# A leitura de variáveis de ambiente no topo é segura
GA_CREDENTIALS_JSON = os.environ.get("GA_CREDENTIALS_JSON")

def _get_google_credentials() -> Credentials:
    """Carrega as credenciais do Google a partir das variáveis de ambiente."""
    if not GA_CREDENTIALS_JSON:
        raise RuntimeError("A variável de ambiente GA_CREDENTIALS_JSON não foi configurada.")
    
    try:
        info = json.loads(GA_CREDENTIALS_JSON)
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    except json.JSONDecodeError:
        raise RuntimeError("O conteúdo em GA_CREDENTIALS_JSON não é um JSON válido.")
    except Exception as e:
        raise RuntimeError(f"Erro ao carregar credenciais: {e}")

def _upload_xlsx_and_convert_to_sheet(filename: str, xlsx_bytes: bytes) -> str | None:
    """
    Faz o upload de um arquivo .xlsx em bytes para o Google Drive e o converte
    para o formato Google Sheets, retornando o link de visualização.
    """
    try:
        creds = _get_google_credentials()
        service = build('drive', 'v3', credentials=creds)

        file_metadata = {
            'name': filename,
            'mimeType': 'application/vnd.google-apps.spreadsheet'
        }
        
        media = MediaIoBaseUpload(
            BytesIO(xlsx_bytes),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            resumable=True
        )

        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='webViewLink'
        ).execute()

        # Garante que o arquivo seja publicamente acessível (qualquer pessoa com o link)
        permission = {'type': 'anyone', 'role': 'reader'}
        service.permissions().create(fileId=file.get('id'), body=permission).execute()

        return file.get('webViewLink')

    except HttpError as error:
        print(f"Ocorreu um erro na API do Google Drive: {error}")
        return None
    except Exception as e:
        print(f"Ocorreu um erro inesperado no upload para o Google Drive: {e}")
        return None


# --- Classe de Serviço ---

class RelatorioService:
    """
    Serviços para geração e manipulação de relatórios.
    """

    @staticmethod
    def get_horas_aula_por_instrutor(
        data_inicio: date, 
        data_fim: date, 
        is_rr_filter: bool, 
        instrutor_ids_filter: List[int] | None
    ) -> List[Dict[str, Any]]:
        """
        Busca e formata os dados de horas-aula por instrutor.
        """
        # --- CORREÇÃO APLICADA AQUI ---
        # Importamos os modelos do banco de dados DENTRO da função.
        # Isso evita o erro de contexto do aplicativo Flask durante a inicialização.
        from ..models import db, Horario, User, Instrutor, Disciplina
        from sqlalchemy import func

        query = (
            db.session.query(
                User.posto_graduacao,
                User.matricula,
                User.nome_completo,
                Disciplina.nome.label('disciplina_nome'),
                func.sum(Horario.carga_horaria).label('ch_a_pagar'),
                Disciplina.carga_horaria.label('ch_total')
            )
            .join(Instrutor, User.id == Instrutor.user_id)
            .join(Horario, Instrutor.id == Horario.instrutor_id)
            .join(Disciplina, Horario.disciplina_id == Disciplina.id)
            .filter(Horario.data.between(data_inicio, data_fim))
            .group_by(
                User.posto_graduacao,
                User.matricula,
                User.nome_completo,
                Disciplina.nome,
                Disciplina.carga_horaria
            )
            .order_by(User.nome_completo)
        )
        
        if is_rr_filter:
            # Assumindo que a coluna se chama `is_rr` no modelo User
            query = query.filter(User.is_rr == True)

        if instrutor_ids_filter:
            query = query.filter(Instrutor.id.in_(instrutor_ids_filter))

        resultados_db = query.all()

        dados_agrupados = {}
        for r in resultados_db:
            matricula = r.matricula or r.nome_completo # Chave alternativa se a matrícula for nula
            if matricula not in dados_agrupados:
                dados_agrupados[matricula] = {
                    "info": {
                        "user": {
                            "posto_graduacao": r.posto_graduacao,
                            "matricula": r.matricula,
                            "nome_completo": r.nome_completo,
                        }
                    },
                    "disciplinas": []
                }
            
            dados_agrupados[matricula]["disciplinas"].append({
                "nome": r.disciplina_nome,
                "ch_total": r.ch_total or 0,
                "ch_paga_anteriormente": 0,
                "ch_a_pagar": r.ch_a_pagar or 0,
            })
            
        return list(dados_agrupados.values())


    @staticmethod
    def export_to_google_sheets(contexto: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Gera o relatório .xlsx formatado e faz o upload para o Google Drive
        como uma Planilha Google.
        """
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
                digitador_nome=contexto.get("digitador_nome", "Digitador"),
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
                return False, "Falha no upload para o Google Drive. Verifique as credenciais e as permissões da API."

        except Exception as e:
            print(f"ERRO CRÍTICO ao exportar para Google Sheets: {e}")
            return False, f"Ocorreu um erro interno: {e}"