import sys
import os
from sqlalchemy import text, inspect

# Adiciona o diretório atual ao path
sys.path.append(os.getcwd())

# Bloco de Importação da App
try:
    from backend.app import create_app
    app = create_app()
except ImportError:
    from backend.app import app

from backend.models.database import db

def forcar_atualizacao_ciclos():
    with app.app_context():
        print("="*50)
        print("FORÇANDO ATUALIZAÇÃO DA TABELA 'ciclos'")
        print("="*50)
        
        inspector = inspect(db.engine)
        colunas_existentes = [c['name'] for c in inspector.get_columns('ciclos')]
        print(f"Colunas atuais em 'ciclos': {colunas_existentes}")

        # COLUNAS A ADICIONAR NA TABELA CICLOS
        # Tipo DATE, permitindo NULL inicialmente para não quebrar dados existentes
        novas_colunas = [
            ("data_inicio", "DATE NULL"),
            ("data_fim", "DATE NULL")
        ]

        with db.engine.connect() as conn:
            conn.begin() # Inicia transação
            for nome_col, tipo_sql in novas_colunas:
                if nome_col not in colunas_existentes:
                    print(f" > Criando coluna '{nome_col}'...")
                    try:
                        sql = text(f"ALTER TABLE ciclos ADD COLUMN {nome_col} {tipo_sql}")
                        conn.execute(sql)
                        print(f"   [SUCESSO] Coluna '{nome_col}' criada.")
                    except Exception as e:
                        print(f"   [ERRO] Falha ao criar '{nome_col}': {e}")
                else:
                    print(f" > Coluna '{nome_col}' já existe.")
            
            conn.commit()
            print("\nProcesso de atualização de ciclos concluído.")

if __name__ == "__main__":
    forcar_atualizacao_ciclos()