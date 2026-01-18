import sys
import os
from sqlalchemy import text

sys.path.append(os.getcwd())
from backend.app import create_app
from backend.models.database import db

app = create_app()

def forcar_migracao():
    with app.app_context():
        print(">>> FORÇANDO MIGRAÇÃO DE COLUNAS...")
        
        comandos = [
            "ALTER TABLE processos_disciplina ADD COLUMN is_crime BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE processos_disciplina ADD COLUMN origem_punicao VARCHAR(20) DEFAULT 'NPCCAL';",
            "ALTER TABLE processos_disciplina MODIFY COLUMN codigo_infracao VARCHAR(50);",
            # Se status for enum no banco, talvez precise alterar, mas geralmente é varchar
            # Se der erro de 'Duplicate column', ignoramos.
        ]
        
        with db.engine.connect() as conn:
            for sql in comandos:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                    print(f"✅ Executado: {sql}")
                except Exception as e:
                    if "Duplicate column" in str(e) or "already exists" in str(e):
                        print(f"⚠️ Já existe: {sql}")
                    else:
                        print(f"❌ Erro em '{sql}': {e}")

if __name__ == "__main__":
    forcar_migracao()