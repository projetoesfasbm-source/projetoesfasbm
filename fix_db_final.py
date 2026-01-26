from backend.app import create_app
from backend.models.database import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print(">>> Verificando e corrigindo colunas na tabela 'processos_disciplina'...")
    
    # Lista de colunas essenciais para o funcionamento correto
    colunas_necessarias = {
        "fundamentacao": "TEXT",
        "detalhes_sancao": "TEXT",
        "decisao_final": "VARCHAR(50)",
        "tipo_sancao": "VARCHAR(50)",
        "observacao_decisao": "TEXT"  # Campo legado, manter por segurança
    }

    with db.engine.connect() as conn:
        # Pega colunas existentes
        result = conn.execute(text("DESCRIBE processos_disciplina"))
        colunas_existentes = [row[0] for row in result.fetchall()]
        
        for col, tipo in colunas_necessarias.items():
            if col not in colunas_existentes:
                print(f"Adicionando coluna faltante: {col} ({tipo})")
                try:
                    conn.execute(text(f"ALTER TABLE processos_disciplina ADD COLUMN {col} {tipo}"))
                    conn.commit()
                    print(f"✔ Coluna {col} adicionada com sucesso.")
                except Exception as e:
                    print(f"Erro ao adicionar {col}: {e}")
            else:
                print(f"✔ Coluna {col} já existe.")

    print("\n>>> Banco de dados verificado.")