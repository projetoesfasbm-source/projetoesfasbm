import sys
import os
from sqlalchemy import text, inspect

# Adiciona o diretório atual ao path
sys.path.append(os.getcwd())

try:
    from backend.app import create_app
    app = create_app()
except ImportError:
    from backend.app import app

from backend.models.database import db

def forcar_atualizacao():
    with app.app_context():
        print("="*50)
        print("FORÇANDO ATUALIZAÇÃO DA TABELA 'processos_disciplina'")
        print("="*50)
        
        inspector = inspect(db.engine)
        colunas_existentes = [c['name'] for c in inspector.get_columns('processos_disciplina')]
        print(f"Colunas atuais: {colunas_existentes}")

        # 1. ADICIONAR COLUNAS FALTANTES
        # ------------------------------
        novas_colunas = [
            ("is_crime", "BOOLEAN NOT NULL DEFAULT 0"),
            ("tipo_sancao", "VARCHAR(50) NULL"),
            ("dias_sancao", "INT NULL"),
            ("origem_punicao", "VARCHAR(20) NOT NULL DEFAULT 'NPCCAL'")
        ]

        with db.engine.connect() as conn:
            conn.begin()
            for nome_col, tipo_sql in novas_colunas:
                if nome_col not in colunas_existentes:
                    print(f" > Criando coluna '{nome_col}'...")
                    try:
                        sql = text(f"ALTER TABLE processos_disciplina ADD COLUMN {nome_col} {tipo_sql}")
                        conn.execute(sql)
                        print(f"   [SUCESSO] Coluna '{nome_col}' criada.")
                    except Exception as e:
                        print(f"   [ERRO] Falha ao criar '{nome_col}': {e}")
                else:
                    print(f" > Coluna '{nome_col}' já existe.")
            
            # 2. CORRIGIR O STATUS (ENUM -> STRING)
            # -------------------------------------
            # Isso resolve o conflito que você suspeitou. Forçamos ser VARCHAR(50).
            print("\n > Convertendo coluna 'status' para VARCHAR(50) (Remove Enum)...")
            try:
                # Comando para MySQL
                sql_status = text("ALTER TABLE processos_disciplina MODIFY COLUMN status VARCHAR(50) NOT NULL DEFAULT 'Aguardando Ciência'")
                conn.execute(sql_status)
                print("   [SUCESSO] Coluna 'status' convertida para Texto.")
            except Exception as e:
                print(f"   [ERRO] Falha ao converter 'status': {e}")

            # Commit das alterações manuais
            conn.commit()
            print("\nProcesso de força bruta concluído.")

if __name__ == "__main__":
    forcar_atualizacao()