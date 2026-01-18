import sys
import os
from sqlalchemy import text

sys.path.append(os.getcwd())
from backend.app import create_app
from backend.models.database import db

app = create_app()

def reparar_banco():
    with app.app_context():
        print(">>> INICIANDO REPARO DO BANCO DE DADOS...")
        
        comandos = [
            # 1. Adiciona a coluna data_registro que está faltando
            "ALTER TABLE processos_disciplina ADD COLUMN data_registro DATETIME NULL DEFAULT CURRENT_TIMESTAMP;",
            
            # 2. Garante as outras colunas novas (caso a migração anterior tenha falhado parcialmente)
            "ALTER TABLE processos_disciplina ADD COLUMN is_crime BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE processos_disciplina ADD COLUMN origem_punicao VARCHAR(20) DEFAULT 'NPCCAL';",
            "ALTER TABLE processos_disciplina MODIFY COLUMN codigo_infracao VARCHAR(50);"
        ]
        
        with db.engine.connect() as conn:
            for sql in comandos:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                    print(f"✅ Sucesso: {sql}")
                except Exception as e:
                    if "Duplicate column" in str(e) or "already exists" in str(e):
                        print(f"⚠️ Já existe (Ignorado): {sql}")
                    else:
                        print(f"❌ Erro ao executar '{sql}': {e}")

if __name__ == "__main__":
    reparar_banco()