from backend.app import create_app, db
from sqlalchemy import text

# Cria a instância da aplicação usando a fábrica
app = create_app()

def fix_database():
    with app.app_context():
        print("--- Iniciando verificação do Banco de Dados (Ciclos) ---")
        try:
            # Tenta selecionar a coluna para ver se ela existe
            db.session.execute(text("SELECT school_id FROM ciclos LIMIT 1"))
            print("SUCESSO: A coluna 'school_id' já existe na tabela 'ciclos'. Nenhuma ação necessária.")
        except Exception:
            print("AVISO: Coluna 'school_id' não encontrada em 'ciclos'. Tentando criar...")
            try:
                # O rollback é necessário para limpar o erro da tentativa anterior
                db.session.rollback()
                
                # 1. Adiciona a coluna
                print("1. Adicionando coluna school_id...")
                db.session.execute(text("ALTER TABLE ciclos ADD COLUMN school_id INTEGER NOT NULL DEFAULT 1"))
                
                # 2. Adiciona a chave estrangeira (Foreign Key)
                print("2. Criando vínculo com tabela schools...")
                db.session.execute(text("ALTER TABLE ciclos ADD CONSTRAINT fk_ciclos_schools FOREIGN KEY (school_id) REFERENCES schools(id)"))
                
                db.session.commit()
                print("CONCLUÍDO: Tabela 'ciclos' atualizada com sucesso!")
            except Exception as e:
                db.session.rollback()
                print(f"ERRO CRÍTICO ao tentar alterar o banco: {str(e)}")

if __name__ == "__main__":
    fix_database()