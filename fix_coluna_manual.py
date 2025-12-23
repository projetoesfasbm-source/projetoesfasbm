# fix_coluna_manual.py
import sys
import os

# Adiciona o diretório atual ao path para conseguir importar o backend
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("Iniciando verificação do banco de dados...")
    try:
        # Tenta executar o comando SQL direto para criar a coluna
        with db.engine.connect() as conn:
            # O comando abaixo adiciona a coluna 'periodo' na tabela 'diarios_classe'
            conn.execute(text("ALTER TABLE diarios_classe ADD COLUMN periodo INT NULL;"))
            conn.commit()
            
        print("SUCESSO: Coluna 'periodo' adicionada à tabela 'diarios_classe'.")
    
    except Exception as e:
        # Se der erro, verificamos se é porque a coluna já existe
        erro_str = str(e).lower()
        if "duplicate column name" in erro_str or "exists" in erro_str:
            print("AVISO: A coluna 'periodo' já existe no banco. Nenhuma ação necessária.")
        else:
            print(f"ERRO: Não foi possível alterar a tabela. Detalhes: {e}")

    print("Concluído.")