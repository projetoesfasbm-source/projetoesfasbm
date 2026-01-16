from backend.app import create_app, db
from sqlalchemy import text

app = create_app()

def fix_database():
    with app.app_context():
        print("Iniciando correção da tabela 'instrutores'...")
        
        sql = "ALTER TABLE instrutores ADD COLUMN assinatura_padrao_path VARCHAR(255) NULL;"
        
        try:
            with db.engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()
            print("SUCESSO: Coluna 'assinatura_padrao_path' adicionada com sucesso!")
        except Exception as e:
            if "Duplicate column name" in str(e):
                print("AVISO: A coluna já existe. Nenhuma ação necessária.")
            else:
                print(f"ERRO: {e}")

if __name__ == "__main__":
    fix_database()