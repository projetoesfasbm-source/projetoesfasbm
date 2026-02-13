import os
import datetime
import zipfile
import subprocess
import glob
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv

# --- CONFIGURAÇÕES ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(BASE_DIR, "backups_sistema_full")
ENV_FILE = os.path.join(BASE_DIR, ".env")

# Pastas que NÃO entram no backup (para economizar espaço)
PASTAS_IGNORAR = {
    'backups_sistema_full', 
    '__pycache__', 
    '.git', 
    'venv', 
    '.cache', 
    'node_modules',
    'tmp'
}

def extrair_credenciais_url():
    """Lê o .env e extrai dados da DATABASE_URL complexa"""
    if not os.path.exists(ENV_FILE):
        print(f"❌ Erro: Arquivo .env não encontrado em: {ENV_FILE}")
        return None

    # Carrega as variáveis
    load_dotenv(ENV_FILE)
    
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("❌ Erro: DATABASE_URL não encontrada no .env")
        return None

    try:
        # Ajuste para o urlparse entender o schema do SQLAlchemy
        url_limpa = database_url.replace("mysql+mysqldb://", "mysql://")
        
        # Remove aspas extras se existirem na string carregada
        url_limpa = url_limpa.strip("'").strip('"')
        
        parsed = urlparse(url_limpa)
        
        # Extrai e decodifica (transforma %23 em #, etc)
        config = {
            'user': parsed.username,
            'password': unquote(parsed.password) if parsed.password else None,
            'host': parsed.hostname,
            'db': parsed.path.lstrip('/')
        }
        
        # Remove parâmetros extras da URL (ex: ?charset=utf8mb4)
        if '?' in config['db']:
            config['db'] = config['db'].split('?')[0]
            
        return config
        
    except Exception as e:
        print(f"❌ Erro ao processar DATABASE_URL: {e}")
        return None

def criar_backup_completo():
    print("="*60)
    print(f"🔄 INICIANDO BACKUP (PythonAnywhere Optimized)")
    print("="*60)

    # 1. Configurar Credenciais
    db_config = extrair_credenciais_url()
    if not db_config:
        return

    # 2. Preparar Pastas
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

    data_hora = datetime.datetime.now().strftime("%Y-%m-%d_%Hh%M")
    nome_zip = os.path.join(BACKUP_DIR, f"backup_full_{data_hora}.zip")
    arquivo_sql_temp = os.path.join(BASE_DIR, "db_dump_temp.sql")

    # 3. Dump do Banco de Dados
    print(f"   💾 Exportando Banco: {db_config['db']}...")
    print(f"      Host: {db_config['host']}")
    
    # Prepara o ambiente para passar a senha de forma segura (sem warning)
    env_dump = os.environ.copy()
    env_dump['MYSQL_PWD'] = db_config['password']

    cmd_db = [
        'mysqldump',
        f'-h{db_config["host"]}',
        f'-u{db_config["user"]}',
        '--column-statistics=0', # Necessário para compatibilidade no PythonAnywhere
        '--no-tablespaces',      # Evita erro de permissão comum
        db_config['db'],
        f'--result-file={arquivo_sql_temp}'
    ]

    try:
        subprocess.run(cmd_db, env=env_dump, check=True, stderr=subprocess.PIPE)
        print("   ✅ Banco de dados exportado com sucesso.")
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Falha no mysqldump (Código {e.returncode})")
        # Não imprimimos o stderr completo para não vazar dados sensíveis em caso de erro bizarro
        if os.path.exists(arquivo_sql_temp): os.remove(arquivo_sql_temp)
        return

    # 4. Compactar Tudo
    print("   📦 Compactando arquivos...")
    try:
        with zipfile.ZipFile(nome_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Adiciona o SQL
            zipf.write(arquivo_sql_temp, arcname="banco_dados.sql")
            
            # Adiciona arquivos do projeto
            for root, dirs, files in os.walk(BASE_DIR):
                dirs[:] = [d for d in dirs if d not in PASTAS_IGNORAR]
                
                for file in files:
                    if file == "db_dump_temp.sql" or file.endswith('.zip') or file.endswith('.log'):
                        continue
                        
                    caminho_completo = os.path.join(root, file)
                    caminho_relativo = os.path.relpath(caminho_completo, BASE_DIR)
                    try:
                        zipf.write(caminho_completo, arcname=caminho_relativo)
                    except OSError:
                        pass 

        print(f"   ✅ Backup Criado: {os.path.basename(nome_zip)}")
        
    except Exception as e:
        print(f"   ❌ Erro na compactação: {e}")
    finally:
        # Limpeza do SQL temporário
        if os.path.exists(arquivo_sql_temp):
            os.remove(arquivo_sql_temp)

    # 5. Rotação (Manter 3)
    aplicar_rotacao()

def aplicar_rotacao():
    print("   🧹 Verificando arquivos antigos...")
    arquivos = sorted(
        glob.glob(os.path.join(BACKUP_DIR, "backup_full_*.zip")),
        key=os.path.getmtime
    )

    while len(arquivos) > 3:
        arquivo_velho = arquivos.pop(0)
        try:
            os.remove(arquivo_velho)
            print(f"   🗑️ Removido antigo: {os.path.basename(arquivo_velho)}")
        except Exception as e:
            print(f"   ⚠️ Erro ao deletar: {e}")

    print("\n✅ PROCESSO FINALIZADO.")

if __name__ == "__main__":
    criar_backup_completo()