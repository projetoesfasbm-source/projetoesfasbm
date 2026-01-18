import sys
import os
from sqlalchemy import text

sys.path.append(os.getcwd())
from backend.app import create_app
from backend.models.database import db

app = create_app()

def run_migration():
    with app.app_context():
        with db.engine.connect() as conn:
            print("--- CORRIGINDO TABELA FADA_AVALIACOES ---")
            
            # Lista completa de colunas novas necessárias
            cols = [
                "ALTER TABLE fada_avaliacoes ADD COLUMN lancador_id INTEGER;",
                "ALTER TABLE fada_avaliacoes ADD COLUMN presidente_id INTEGER;",
                "ALTER TABLE fada_avaliacoes ADD COLUMN membro1_id INTEGER;",
                "ALTER TABLE fada_avaliacoes ADD COLUMN membro2_id INTEGER;",
                "ALTER TABLE fada_avaliacoes ADD COLUMN status VARCHAR(20) DEFAULT 'RASCUNHO';",
                "ALTER TABLE fada_avaliacoes ADD COLUMN etapa_atual VARCHAR(50) DEFAULT 'RASCUNHO';",
                "ALTER TABLE fada_avaliacoes ADD COLUMN ndisc_snapshot FLOAT DEFAULT 0;",
                "ALTER TABLE fada_avaliacoes ADD COLUMN aat_snapshot FLOAT DEFAULT 0;",
                "ALTER TABLE fada_avaliacoes ADD COLUMN data_envio DATETIME;",
                # Assinaturas Comissão
                "ALTER TABLE fada_avaliacoes ADD COLUMN data_ass_pres DATETIME;",
                "ALTER TABLE fada_avaliacoes ADD COLUMN hash_pres VARCHAR(100);",
                "ALTER TABLE fada_avaliacoes ADD COLUMN ip_pres VARCHAR(45);",
                "ALTER TABLE fada_avaliacoes ADD COLUMN data_ass_m1 DATETIME;",
                "ALTER TABLE fada_avaliacoes ADD COLUMN hash_m1 VARCHAR(100);",
                "ALTER TABLE fada_avaliacoes ADD COLUMN ip_m1 VARCHAR(45);",
                "ALTER TABLE fada_avaliacoes ADD COLUMN data_ass_m2 DATETIME;",
                "ALTER TABLE fada_avaliacoes ADD COLUMN hash_m2 VARCHAR(100);",
                "ALTER TABLE fada_avaliacoes ADD COLUMN ip_m2 VARCHAR(45);",
                # Assinatura Aluno
                "ALTER TABLE fada_avaliacoes ADD COLUMN data_assinatura DATETIME;",
                "ALTER TABLE fada_avaliacoes ADD COLUMN ip_assinatura VARCHAR(45);",
                "ALTER TABLE fada_avaliacoes ADD COLUMN user_agent_aluno VARCHAR(255);",
                "ALTER TABLE fada_avaliacoes ADD COLUMN hash_integridade VARCHAR(100);",
                "ALTER TABLE fada_avaliacoes ADD COLUMN texto_recurso TEXT;"
            ]

            for sql in cols:
                try:
                    conn.execute(text(sql))
                    print(f"[OK] Executado: {sql}")
                except Exception as e:
                    if "Duplicate column" in str(e) or "already exists" in str(e):
                        print(f"[INFO] Coluna já existe (Ignorado).")
                    else:
                        print(f"[ERRO] {e}")

            conn.commit()
            print("--- BANCO ATUALIZADO COM SUCESSO ---")

if __name__ == "__main__":
    run_migration()