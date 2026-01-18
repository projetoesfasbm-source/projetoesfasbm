import sys
import os
from sqlalchemy import text

# Adiciona o diretório atual ao path para garantir que encontre o backend
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db

app = create_app()

def run_migration():
    with app.app_context():
        with db.engine.connect() as conn:
            print("--- Iniciando Atualização da Tabela fada_avaliacoes ---")
            
            # Lista de colunas novas necessárias para o novo fluxo
            comandos_sql = [
                # 1. Campos da Comissão de Avaliação
                "ALTER TABLE fada_avaliacoes ADD COLUMN lancador_id INTEGER;",
                "ALTER TABLE fada_avaliacoes ADD COLUMN presidente_id INTEGER;",
                "ALTER TABLE fada_avaliacoes ADD COLUMN membro1_id INTEGER;",
                "ALTER TABLE fada_avaliacoes ADD COLUMN membro2_id INTEGER;",
                
                # 2. Campos de Fluxo e Auditoria
                "ALTER TABLE fada_avaliacoes ADD COLUMN status VARCHAR(20) DEFAULT 'RASCUNHO';",
                "ALTER TABLE fada_avaliacoes ADD COLUMN ndisc_snapshot FLOAT DEFAULT 0;",
                "ALTER TABLE fada_avaliacoes ADD COLUMN aat_snapshot FLOAT DEFAULT 0;",
                "ALTER TABLE fada_avaliacoes ADD COLUMN data_envio DATETIME;",
                "ALTER TABLE fada_avaliacoes ADD COLUMN data_assinatura DATETIME;",
                "ALTER TABLE fada_avaliacoes ADD COLUMN ip_assinatura VARCHAR(45);",
                "ALTER TABLE fada_avaliacoes ADD COLUMN user_agent_aluno VARCHAR(255);",
                "ALTER TABLE fada_avaliacoes ADD COLUMN hash_integridade VARCHAR(100);",
                "ALTER TABLE fada_avaliacoes ADD COLUMN texto_recurso TEXT;"
            ]

            for sql in comandos_sql:
                try:
                    conn.execute(text(sql))
                    print(f"[SUCESSO] {sql}")
                except Exception as e:
                    # Ignora erro se a coluna já existir (OperationalError)
                    if "duplicate column" in str(e) or "already exists" in str(e):
                        print(f"[INFO] Coluna já existe, pulando: {sql}")
                    else:
                        print(f"[AVISO] Erro ao tentar executar '{sql}': {e}")

            conn.commit()
            print("--- Migração Finalizada ---")

if __name__ == "__main__":
    run_migration()