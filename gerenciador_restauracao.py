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
    # Tenta importar o parser de URL do SQLAlchemy (compatível com várias versões)
    try:
        from sqlalchemy.engine import make_url
    except ImportError:
        from sqlalchemy.engine.url import make_url
        
    app = create_app()
except Exception as e:
    print(f"Erro ao carregar app Flask: {e}")
    sys.exit(1)

def listar_backups():
    print("\n" + "="*60)
    print("GERENCIADOR DE RESTAURAÇÃO DE BACKUP (CORRIGIDO)")
    print("="*60)
    print("Procurando arquivos .sql na pasta atual...\n")

    arquivos = glob.glob(os.path.join(basedir, "*.sql"))
    
    if not arquivos:
        print(">> NENHUM ARQUIVO .sql ENCONTRADO!")
        return None

    backups = []
    print(f"{'Índice':<6} | {'Data/Hora Criação':<20} | {'Nome do Arquivo'}")
    print("-" * 60)
    
    # Ordena por data de modificação (mais recente primeiro)
    arquivos.sort(key=os.path.getmtime, reverse=True)
    
    for i, arq in enumerate(arquivos):
        timestamp = os.path.getmtime(arq)
        data_hora = datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y %H:%M:%S')
        nome = os.path.basename(arq)
        backups.append(arq)
        print(f"{i+1:<6} | {data_hora:<20} | {nome}")
    
    print("-" * 60)
    return backups

def restaurar_backup(arquivo_path):
    print(f"\nPREPARANDO PARA RESTAURAR: {os.path.basename(arquivo_path)}")
    print("⚠️  ATENÇÃO: Isso vai apagar TUDO que foi feito após essa data.")
    
    confirm = input("Digite 'RESTAURAR' para confirmar (ou Enter para cancelar): ")
    if confirm != 'RESTAURAR':
        print("Cancelado.")
        return

    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
    
    if not db_uri:
        print("Erro: URI do banco não encontrada.")
        return

    try:
        # USA O PARSER OFICIAL (Resolve o problema da senha com @)
        url = make_url(db_uri)
        
        # Extrai os dados de forma segura
        host = url.host
        user = url.username
        password = url.password
        db_name = url.database
        port = url.port or 3306

        print(f"\nConectando ao banco '{db_name}' no host '{host}'...")

        # Monta comando do mysql
        cmd = [
            'mysql',
            f'-h{host}',
            f'-P{port}',
            f'-u{user}',
            f'-p{password}',
            db_name
        ]

        print(">> Executando restauração... Aguarde...")
        
        with open(arquivo_path, 'r') as f:
            # Executa o comando e captura erros se houver
            process = subprocess.Popen(cmd, stdin=f, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()

        if process.returncode == 0:
            print("\n" + "="*60)
            print("✅ SUCESSO! O BANCO DE DADOS FOI RESTAURADO.")
            print("="*60)
            print("O sistema voltou exatamente para o estado do arquivo escolhido.")
        else:
            print("\n❌ ERRO NA RESTAURAÇÃO:")
            print(stderr.decode('utf-8', errors='ignore'))

    except Exception as e:
        print(f"Erro ao processar a conexão: {e}")

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