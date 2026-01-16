# migrate_assinatura_padrao.py
from backend.app import create_app, db
from sqlalchemy import text

app = create_app()

def migrate():
    with app.app_context():
        print("Adicionando campo 'assinatura_padrao_path' na tabela 'instrutores'...")
        try:
            with db.engine.connect() as conn:
                # Verifica se a coluna já existe
                columns = conn.execute(text("SHOW COLUMNS FROM instrutores LIKE 'assinatura_padrao_path'")).fetchall()
                if not columns:
                    conn.execute(text("ALTER TABLE instrutores ADD COLUMN assinatura_padrao_path VARCHAR(255) NULL"))
                    conn.commit()
                    print("Coluna criada com sucesso.")
                else:
                    print("Coluna já existe.")
        except Exception as e:
            print(f"Erro na migração: {e}")

if __name__ == "__main__":
    migrate()