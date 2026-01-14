# fix_db_manual.py
from backend.app import create_app
from backend.models.database import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("Iniciando correção manual do banco de dados...")
    
    try:
        # 1. Tenta adicionar a coluna atributo_fada_id na tabela discipline_rules
        print("Tentando adicionar coluna 'atributo_fada_id' em 'discipline_rules'...")
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE discipline_rules ADD COLUMN atributo_fada_id INT DEFAULT NULL;"))
            conn.commit()
        print("Sucesso: Coluna adicionada.")
    except Exception as e:
        print(f"Aviso (pode ignorar se já existir): {e}")

    try:
        # 2. Tenta criar a tabela elogios se não existir
        print("Verificando tabela 'elogios'...")
        with db.engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS elogios (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    aluno_id INT NOT NULL,
                    registrado_por_id INT NOT NULL,
                    data_elogio DATE NOT NULL,
                    data_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
                    descricao TEXT NOT NULL,
                    pontos FLOAT NOT NULL DEFAULT 0.0,
                    atributo_1 INT,
                    atributo_2 INT,
                    FOREIGN KEY (aluno_id) REFERENCES alunos(id),
                    FOREIGN KEY (registrado_por_id) REFERENCES users(id)
                );
            """))
            conn.commit()
        print("Sucesso: Tabela elogios verificada/criada.")
    except Exception as e:
        print(f"Erro ao criar tabela elogios: {e}")

    print("Concluído.")