# backend/export_to_sheets.py

from __future__ import annotations
import os
import json
import pandas as pd
from typing import Dict
from sqlalchemy import create_engine, text
from google.oauth2.service_account import Credentials
import gspread

# Opcional, mas recomendado: escrita performática
try:
    from gspread_dataframe import set_with_dataframe
    HAS_DF_HELPER = True
except Exception:
    HAS_DF_HELPER = False

# -----------------------------------------------------------------------------
# Configurações via variáveis de ambiente (evita segredos no código)
# Defina no PythonAnywhere:
#   export GA_SHEETS_ID="..."            (ID da planilha)
#   export GA_CREDENTIALS_JSON="..."     (conteúdo do credentials.json inteiro)
#   export DB_USER="..."
#   export DB_PASSWORD="..."
#   export DB_HOST="esfasBM.mysql.pythonanywhere-services.com"
#   export DB_NAME="esfasBM$default"
# -----------------------------------------------------------------------------

ID_PLANILHA = os.environ.get("GA_SHEETS_ID") or "COLOQUE_AQUI_SEM_ENV"
GA_CREDENTIALS_JSON = os.environ.get("GA_CREDENTIALS_JSON")  # conteúdo do JSON
PATH_CREDENCIAS_GOOGLE = os.environ.get("GA_CREDENTIALS_PATH")  # caminho opcional

DB_USER = os.environ.get("DB_USER", "esfasBM")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_HOST = os.environ.get("DB_HOST", "esfasBM.mysql.pythonanywhere-services.com")
DB_NAME = os.environ.get("DB_NAME", "esfasBM$default")

# Tabelas -> Abas
TABELAS_PARA_EXPORTAR: Dict[str, str] = {
    'alembic_version': 'Alembic_Version',
    'alunos': 'Alunos',
    'ciclos': 'Ciclos',
    'disciplina_turmas': 'Disciplina_Turmas',
    'disciplinas': 'Disciplinas',
    'historico_alunos': 'Historico_Alunos',
    'historico_disciplinas': 'Historico_Disciplinas',
    'horarios': 'Horarios',
    'image_assets': 'Image_Assets',
    'instrutores': 'Instrutores',
    'opcoes_respostas': 'Opcoes_Respostas',
    'password_reset_tokens': 'Password_Reset_Tokens',
    'perguntas': 'Perguntas',
    'questionarios': 'Questionarios',
    'respostas': 'Respostas',
    'schools': 'Schools',
    'semanas': 'Semanas',
    'site_configs': 'Site_Configs',
    'turma_cargos': 'Turma_Cargos',
    'turmas': 'Turmas',
    'user_schools': 'User_Schools',
    'users': 'Usuarios'
}

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def _load_google_credentials() -> Credentials:
    """
    Carrega credenciais do Google a partir de:
      - GA_CREDENTIALS_JSON (conteúdo do JSON em string) OU
      - GA_CREDENTIALS_PATH (caminho do arquivo) OU
      - PATH_CREDENCIAS_GOOGLE legado
    """
    if GA_CREDENTIALS_JSON:
        info = json.loads(GA_CREDENTIALS_JSON)
        return Credentials.from_service_account_info(info, scopes=SCOPES)

    path = PATH_CREDENCIAS_GOOGLE or os.environ.get("PATH_CREDENCIAS_GOOGLE")
    if not path:
        raise RuntimeError("Credenciais não configuradas. Defina GA_CREDENTIALS_JSON ou GA_CREDENTIALS_PATH.")

    return Credentials.from_service_account_file(path, scopes=SCOPES)


def _get_engine():
    # Use PyMySQL (garanta pip install pymysql)
    conn_str = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
    return create_engine(conn_str, pool_pre_ping=True)


def _open_spreadsheet(creds: Credentials, spreadsheet_id: str):
    client = gspread.authorize(creds)
    return client.open_by_key(spreadsheet_id)


def _upsert_worksheet(spreadsheet, title: str, rows: int = 1, cols: int = 1):
    try:
        ws = spreadsheet.worksheet(title)
        ws.clear()
        return ws
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=title, rows=str(rows), cols=str(cols))


def exportar_dados():
    print("Iniciando a exportação de TODAS as tabelas para Google Sheets...")

    # Valida ID da planilha
    if not ID_PLANILHA or ID_PLANILHA == "COLOQUE_AQUI_SEM_ENV":
        print("ERRO: GA_SHEETS_ID não configurada. Defina a variável de ambiente GA_SHEETS_ID.")
        return

    # Conecta ao Google
    try:
        creds = _load_google_credentials()
        spreadsheet = _open_spreadsheet(creds, ID_PLANILHA)
        print("Conectado ao Google Sheets.")
    except Exception as e:
        print(f"ERRO ao conectar ao Google Sheets: {repr(e)}")
        return

    # Conecta ao banco
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            # sanity check
            conn.execute(text("SELECT 1"))
        print("Conectado ao MySQL.")
    except Exception as e:
        print(f"ERRO ao conectar ao MySQL: {repr(e)}")
        return

    # Exporta cada tabela
    for nome_tabela, nome_aba in TABELAS_PARA_EXPORTAR.items():
        try:
            print(f"-> Exportando '{nome_tabela}' para aba '{nome_aba}'...")
            with engine.connect() as conn:
                df = pd.read_sql(text(f"SELECT * FROM `{nome_tabela}`"), conn)

            # Normaliza NaN/None
            df = df.fillna("")

            ws = _upsert_worksheet(spreadsheet, nome_aba, rows=max(1, len(df) + 1), cols=max(1, len(df.columns)))

            if HAS_DF_HELPER:
                # Escreve cabeçalho + dados de forma otimizada
                set_with_dataframe(ws, df, include_index=False, include_column_header=True, resize=True)
            else:
                # Fallback: update em uma chamada (pode ser pesado para datasets grandes)
                ws.update([df.columns.tolist()] + df.values.tolist())

            print(f"OK: '{nome_tabela}' exportada.")
        except Exception as e:
            print(f"ERRO na tabela '{nome_tabela}': {repr(e)}")

    print("Exportação concluída.")


if __name__ == "__main__":
    exportar_dados()
