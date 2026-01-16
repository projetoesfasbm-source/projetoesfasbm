# migrate_diario_classe.py
from backend.app import create_app, db
from sqlalchemy import text

app = create_app()

def migrate():
    with app.app_context():
        print("Iniciando migração da tabela 'diarios_classe'...")
        
        # Lista de colunas a adicionar
        new_columns = [
            ("status", "VARCHAR(20) NOT NULL DEFAULT 'pendente'"),
            ("assinatura_path", "VARCHAR(255) NULL"),
            ("data_assinatura", "DATETIME NULL"),
            ("instrutor_assinante_id", "INTEGER NULL"),
            ("created_at", "DATETIME DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "DATETIME DEFAULT CURRENT_TIMESTAMP")
        ]
        
        # Chave estrangeira
        fk_sql = "ALTER TABLE diarios_classe ADD CONSTRAINT fk_diario_instrutor FOREIGN KEY (instrutor_assinante_id) REFERENCES users(id)"

        with db.engine.connect() as conn:
            # Verifica colunas existentes
            existing_columns = conn.execute(text("SHOW COLUMNS FROM diarios_classe")).fetchall()
            existing_col_names = [row[0] for row in existing_columns]
            
            for col_name, col_def in new_columns:
                if col_name not in existing_col_names:
                    print(f"Adicionando coluna: {col_name}")
                    try:
                        conn.execute(text(f"ALTER TABLE diarios_classe ADD COLUMN {col_name} {col_def}"))
                        conn.commit()
                    except Exception as e:
                        print(f"Erro ao adicionar {col_name}: {e}")
                else:
                    print(f"Coluna {col_name} já existe.")

            # Tenta adicionar a FK (pode falhar se já existir, então usamos try/except)
            print("Verificando Constraint FK...")
            try:
                conn.execute(text(fk_sql))
                conn.commit()
                print("FK fk_diario_instrutor adicionada.")
            except Exception as e:
                print(f"Nota: FK pode já existir ou erro: {e}")

        print("Migração concluída.")

if __name__ == "__main__":
    migrate()