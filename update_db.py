# update_db.py
import os
import sys
from sqlalchemy import text

# Adiciona o diretório atual ao path para encontrar o backend
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db

app = create_app()

def atualizar_banco():
    with app.app_context():
        print("Iniciando atualização da tabela 'semanas'...")
        
        with db.engine.connect() as conn:
            # 1. Verifica e adiciona a coluna priority_active
            try:
                print("Verificando coluna 'priority_active'...")
                conn.execute(text("SELECT priority_active FROM semanas LIMIT 1"))
                print(" -> Coluna 'priority_active' já existe.")
            except Exception:
                print(" -> Criando coluna 'priority_active'...")
                conn.execute(text("ALTER TABLE semanas ADD COLUMN priority_active TINYINT(1) DEFAULT 0"))
                conn.commit()
                print(" -> Sucesso!")

            # 2. Verifica e adiciona a coluna priority_disciplines
            try:
                print("Verificando coluna 'priority_disciplines'...")
                conn.execute(text("SELECT priority_disciplines FROM semanas LIMIT 1"))
                print(" -> Coluna 'priority_disciplines' já existe.")
            except Exception:
                print(" -> Criando coluna 'priority_disciplines'...")
                conn.execute(text("ALTER TABLE semanas ADD COLUMN priority_disciplines TEXT DEFAULT NULL"))
                conn.commit()
                print(" -> Sucesso!")

        print("\nProcesso finalizado! O banco de dados está atualizado.")

if __name__ == "__main__":
    atualizar_banco()