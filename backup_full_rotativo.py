import os
import datetime
import zipfile
import subprocess
import glob
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv

# --- CONFIGURAÇÕES ---
# Diretório onde este script está (Raiz do Projeto)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Pasta onde os zips serão salvos
BACKUP_DIR = os.path.join(BASE_DIR, "backups_sistema_full")
# Arquivo de senhas
ENV_FILE = os.path.join(BASE_DIR, ".env")

# Pastas para ignorar
PASTAS_IGNORAR = {
    'backups_sistema_full', '__pycache__', '.git', 'venv', '.cache', 'node_modules', 'tmp'
}

def extrair_credenciais_url():
    """Lê credenciais do .env"""
    if not os.path.exists(ENV_FILE):
        print(f"❌ Erro: .env não encontrado em {ENV_FILE}")
        return None
    load_dotenv(ENV_FILE)
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ Erro: DATABASE_URL ausente no .env")
        return None
    try:
        url_limpa = database_url.replace("mysql+mysqldb://", "mysql://").strip("'").strip('"')
        parsed = urlparse(url_limpa)
        config = {
            'user': parsed.username,
            'password': unquote(parsed.password) if parsed.password else None,
            'host': parsed.hostname,
            'db': parsed.path.lstrip('/')
        }
        if '?' in config['db']: config['db'] = config['db'].split('?')[0]
        return config
    except Exception as e:
        print(f"❌ Erro ao ler URL: {e}")
        return None

def criar_backup_completo():
    print("="*60)
    print(f"📦 INICIANDO BACKUP ORGANIZADO (V3.0)")
    print("="*60)

    # 1. Configurar
    db_config = extrair_credenciais_url()
    if not db_config: return

    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

    data_hora = datetime.datetime.now().strftime("%Y-%m-%d_%Hh%M")
    nome_zip = os.path.join(BACKUP_DIR, f"backup_full_{data_hora}.zip")
    arquivo_sql_temp = os.path.join(BASE_DIR, f"backup_banco_{data_hora}.sql")

    # 2. Exportar Banco
    print(f"   💾 Gerando SQL: {os.path.basename(arquivo_sql_temp)}...")
    env_dump = os.environ.copy()
    env_dump['MYSQL_PWD'] = db_config['password']

    cmd_db = [
        'mysqldump',
        f'-h{db_config["host"]}',
        f'-u{db_config["user"]}',
        '--column-statistics=0',
        '--no-tablespaces',
        db_config['db'],
        f'--result-file={arquivo_sql_temp}'
    ]

    try:
        subprocess.run(cmd_db, env=env_dump, check=True, stderr=subprocess.PIPE)
        tamanho_sql = os.path.getsize(arquivo_sql_temp) / (1024*1024)
        print(f"   ✅ SQL Gerado com sucesso ({tamanho_sql:.2f} MB).")
    except subprocess.CalledProcessError:
        print(f"   ❌ Falha ao exportar banco de dados.")
        if os.path.exists(arquivo_sql_temp): os.remove(arquivo_sql_temp)
        return

    # 3. Compactar com Estrutura Organizada
    print("   🗜️  Compactando arquivos...")
    try:
        with zipfile.ZipFile(nome_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # A. Coloca o Banco numa pasta separada dentro do ZIP para destaque
            zipf.write(arquivo_sql_temp, arcname=f"00_BANCO_DE_DADOS/{os.path.basename(arquivo_sql_temp)}")

            # B. Coloca o Código numa pasta 'CODIGO_FONTE'
            for root, dirs, files in os.walk(BASE_DIR):
                dirs[:] = [d for d in dirs if d not in PASTAS_IGNORAR]
                for file in files:
                    if file == os.path.basename(arquivo_sql_temp) or file.endswith('.zip') or file.endswith('.log'):
                        continue

                    caminho_absoluto = os.path.join(root, file)
                    caminho_relativo = os.path.relpath(caminho_absoluto, BASE_DIR)
                    # Adiciona prefixo CODIGO_FONTE para não misturar com o banco
                    zipf.write(caminho_absoluto, arcname=os.path.join("CODIGO_FONTE", caminho_relativo))

        print(f"   ✨ Backup Finalizado: {os.path.basename(nome_zip)}")

    except Exception as e:
        print(f"   ❌ Erro no ZIP: {e}")
    finally:
        if os.path.exists(arquivo_sql_temp):
            os.remove(arquivo_sql_temp)

    # 4. Limpeza
    aplicar_rotacao()

def aplicar_rotacao():
    print("   🧹 Limpando backups antigos...")
    arquivos = sorted(glob.glob(os.path.join(BACKUP_DIR, "backup_full_*.zip")), key=os.path.getmtime)
    while len(arquivos) > 10:
        os.remove(arquivos.pop(0))
        print("      🗑️  Backup antigo removido.")
    print("\n✅ PROCESSO CONCLUÍDO.")

if __name__ == "__main__":
    criar_backup_completo()