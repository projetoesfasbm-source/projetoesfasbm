# fix_prioridade_db.py
import sys
import os
from sqlalchemy import text

sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db

app = create_app()

with app.app_context():
    print("--- VERIFICANDO COLUNAS DE PRIORIDADE ---")
    try:
        with db.engine.connect() as conn:
            # 1. Adiciona prioridade_status se não existir
            try:
                conn.execute(text("ALTER TABLE semanas ADD COLUMN prioridade_status BOOLEAN DEFAULT 0"))
                print("✅ Coluna 'prioridade_status' adicionada.")
            except Exception as e:
                if "Duplicate column" in str(e) or "exists" in str(e):
                    print("ℹ️ Coluna 'prioridade_status' já existe.")
                else:
                    print(f"⚠️ Erro ao adicionar status: {e}")

            # 2. Adiciona prioridade_disciplinas se não existir
            try:
                conn.execute(text("ALTER TABLE semanas ADD COLUMN prioridade_disciplinas TEXT"))
                print("✅ Coluna 'prioridade_disciplinas' adicionada.")
            except Exception as e:
                if "Duplicate column" in str(e) or "exists" in str(e):
                    print("ℹ️ Coluna 'prioridade_disciplinas' já existe.")
                else:
                    print(f"⚠️ Erro ao adicionar disciplinas: {e}")
            
            conn.commit()
            print("--- CONCLUSÃO: Banco de dados atualizado. ---")
            
    except Exception as e:
        print(f"❌ Erro fatal: {e}")