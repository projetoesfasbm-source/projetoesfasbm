# backend/export_to_sheets.py

import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from sqlalchemy import create_engine
import os

# --- CONFIGURAÇÕES ---

# 1. Caminho para o seu arquivo de credenciais do Google
PATH_CREDENCIAS_GOOGLE = '/home/esfasBM/sistema_escolar_deepseak_1/backend/credentials.json'

# 2. ID da sua Planilha Google
ID_PLANILHA = '16X3qOihCsB-pSnqi7ZUYD0r3_MwV1toKWuP30xYtSoQ'

# 3. Nomes de todas as tabelas que você quer exportar.
#    A lista foi atualizada para incluir todas as tabelas do seu banco de dados.
TABELAS_PARA_EXPORTAR = {
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

# 4. Dados de conexão com o seu banco MySQL
DB_USER = 'esfasBM'
DB_PASSWORD = '#a!hndtbztUD7Mi'  # <-- ATENÇÃO: COLOQUE SUA NOVA SENHA AQUI
DB_HOST = 'esfasBM.mysql.pythonanywhere-services.com'
DB_NAME = 'esfasBM$default'

# --- FIM DAS CONFIGURAÇÕES ---

def exportar_dados():
    """Conecta ao banco, lê as tabelas e as envia para o Google Sheets."""
    print("Iniciando a exportação de TODAS as tabelas...")

    # Conectar ao Google Sheets
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(PATH_CREDENCIAS_GOOGLE, scopes=scopes)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(ID_PLANILHA)
        print("Conectado ao Google Sheets com sucesso.")
    except Exception as e:
        print(f"ERRO ao conectar ao Google Sheets: {repr(e)}")
        return

    # Conectar ao Banco de Dados
    try:
        db_connection_str = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}'
        engine = create_engine(db_connection_str)
        print("Conectado ao banco de dados MySQL com sucesso.")
    except Exception as e:
        print(f"ERRO ao conectar ao banco de dados: {repr(e)}")
        return

    # Processar cada tabela
    for nome_tabela, nome_aba in TABELAS_PARA_EXPORTAR.items():
        try:
            print(f"Processando tabela '{nome_tabela}' para a aba '{nome_aba}'...")
            df = pd.read_sql(f"SELECT * FROM {nome_tabela}", engine)

            try:
                worksheet = spreadsheet.worksheet(nome_aba)
                worksheet.clear()
                print(f"Aba '{nome_aba}' limpa.")
            except gspread.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(title=nome_aba, rows=1, cols=1)
                print(f"Aba '{nome_aba}' criada.")

            df = df.fillna('')
            worksheet.update([df.columns.values.tolist()] + df.values.tolist())
            print(f"Tabela '{nome_tabela}' exportada com sucesso!")

        except Exception as e:
            print(f"ERRO ao processar a tabela '{nome_tabela}': {repr(e)}")

    print("\nExportação concluída!")

if __name__ == '__main__':
    exportar_dados()