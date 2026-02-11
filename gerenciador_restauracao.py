import sys
import os
import subprocess
from datetime import datetime
import glob

# --- CONFIGURAÇÃO DE CAMINHO ---
basedir = os.path.abspath(os.path.dirname(__file__))
backend_path = os.path.join(basedir, 'backend')
if os.path.exists(backend_path) and backend_path not in sys.path:
    sys.path.insert(0, backend_path)

try:
    from app import create_app
    app = create_app()
except Exception as e:
    print(f"Erro ao carregar app Flask: {e}")
    sys.exit(1)

def listar_backups():
    print("\n" + "="*60)
    print("GERENCIADOR DE RESTAURAÇÃO DE BACKUP")
    print("="*60)
    print("Procurando arquivos .sql na pasta atual...\n")

    # Busca arquivos .sql
    arquivos = glob.glob(os.path.join(basedir, "*.sql"))
    
    if not arquivos:
        print(">> NENHUM ARQUIVO .sql ENCONTRADO!")
        print("Sem um arquivo de backup, não é possível restaurar o estado anterior.")
        return None

    backups = []
    print(f"{'Índice':<6} | {'Data/Hora Criação':<20} | {'Nome do Arquivo'}")
    print("-" * 60)
    
    for i, arq in enumerate(arquivos):
        # Pega data de modificação
        timestamp = os.path.getmtime(arq)
        data_hora = datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M:%S')
        nome = os.path.basename(arq)
        backups.append(arq)
        print(f"{i+1:<6} | {data_hora:<20} | {nome}")
    
    print("-" * 60)
    return backups

def restaurar_backup(arquivo_path):
    print(f"\nPREPARANDO PARA RESTAURAR: {os.path.basename(arquivo_path)}")
    print("Isso vai SOBRESCREVER o banco de dados atual com os dados deste arquivo.")
    
    confirm = input("Digite 'RESTAURAR' para confirmar (ou Enter para cancelar): ")
    if confirm != 'RESTAURAR':
        print("Cancelado.")
        return

    # Extrair credenciais do Flask App
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
    
    if not db_uri or 'mysql' not in db_uri:
        print("Erro: Não foi possível detectar configuração MySQL válida no app.")
        return

    # Parse simples da URI: mysql://user:pass@host/db
    try:
        # Remove prefixo
        clean = db_uri.replace('mysql://', '').replace('mysql+pymysql://', '')
        
        # Separa user:pass e host/db
        creds, server = clean.split('@')
        user, password = creds.split(':')
        
        # Separa host e db
        if '/' in server:
            host, db_name = server.split('/')
        else:
            host = server
            db_name = "" # Tenta pegar sem
            
        # Remove parâmetros extras se houver (?charset=utf8 etc)
        if '?' in db_name:
            db_name = db_name.split('?')[0]

        print(f"\nConectando ao banco '{db_name}' no host '{host}'...")

        # Monta comando do sistema (mysql client)
        # É mais seguro e rápido usar o comando nativo do que ler linha a linha em Python
        cmd = [
            'mysql',
            f'-h{host}',
            f'-u{user}',
            f'-p{password}',
            db_name
        ]

        print(">> Executando restauração... (Isso pode levar alguns segundos)")
        
        # Executa o comando redirecionando a entrada do arquivo
        with open(arquivo_path, 'r') as f:
            process = subprocess.Popen(cmd, stdin=f, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()

        if process.returncode == 0:
            print("\n" + "="*60)
            print("SUCESSO! O BANCO DE DADOS FOI RESTAURADO.")
            print("="*60)
            print("Verifique o site agora. Tudo deve estar como na data do arquivo.")
        else:
            print("\n[ERRO NA RESTAURAÇÃO]")
            print(stderr.decode('utf-8'))

    except Exception as e:
        print(f"Erro ao processar credenciais ou executar: {e}")

if __name__ == "__main__":
    lista = listar_backups()
    if lista:
        print("\nQual arquivo você deseja restaurar?")
        escolha = input(f"Digite o número (1-{len(lista)}) ou 0 para sair: ")
        
        if escolha.isdigit():
            idx = int(escolha) - 1
            if 0 <= idx < len(lista):
                restaurar_backup(lista[idx])
            else:
                print("Saindo...")
        else:
            print("Opção inválida.")