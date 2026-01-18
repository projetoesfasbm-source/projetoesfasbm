import sys
import os
from sqlalchemy import text

# Ajuste de path
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db

app = create_app()

def forcar_adicao_coluna():
    with app.app_context():
        print(">>> Verificando e Corrigindo Tabela 'turmas'...")
        
        # 1. Tenta adicionar a coluna. Se já existir, vai dar erro e ignoramos.
        sql = text("ALTER TABLE turmas ADD COLUMN data_formatura DATE NULL;")
        
        try:
            with db.engine.connect() as conn:
                conn.execute(sql)
                conn.commit()
            print("✅ SUCESSO: Coluna 'data_formatura' adicionada com força bruta.")
        except Exception as e:
            if "Duplicate column name" in str(e):
                print("⚠️  AVISO: A coluna 'data_formatura' JÁ EXISTE. Tudo certo.")
            else:
                print(f"❌ ERRO CRÍTICO ao alterar tabela: {e}")

if __name__ == "__main__":
    forcar_adicao_coluna()