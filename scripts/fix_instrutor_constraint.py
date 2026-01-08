# scripts/fix_instrutor_constraint.py
import sys
import os

# Ajusta o caminho para incluir a raiz do projeto
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app import create_app
from backend.models.database import db
from sqlalchemy import text

app = create_app()

def fix_db_constraint():
    with app.app_context():
        print("=== Corrigindo Restrição de Unicidade na Tabela Instrutores ===")
        print("O objetivo é permitir que um usuário seja instrutor em mais de uma escola.")
        
        # Tenta descobrir o nome do índice e removê-lo.
        # Em MySQL, geralmente o índice da chave estrangeira única tem o nome da coluna.
        
        try:
            # Primeiro, verificamos se o índice existe (comando específico para MySQL)
            result = db.session.execute(text("SHOW INDEX FROM instrutores WHERE Key_name = 'user_id'")).fetchone()
            
            if result:
                print(" -> Índice 'user_id' encontrado. Removendo restrição UNIQUE...")
                # DROP INDEX remove o índice. Como temos a FK e o índice composto, 
                # o MySQL usará o índice composto (user_id, school_id) para a FK, o que é permitido.
                db.session.execute(text("ALTER TABLE instrutores DROP INDEX user_id"))
                db.session.commit()
                print("SUCCESS: Restrição removida com sucesso!")
            else:
                print("AVISO: Índice 'user_id' não encontrado. Pode ter outro nome ou já ter sido removido.")
                
                # Tentativa de fallback para nomes comuns gerados pelo SQLAlchemy
                try:
                    print(" -> Tentando remover constraint pelo nome 'user_id' (caso seja constraint nomeada)...")
                    db.session.execute(text("ALTER TABLE instrutores DROP CONSTRAINT user_id"))
                    db.session.commit()
                    print("SUCCESS: Constraint removida.")
                except Exception as e_inner:
                    print(f" -> Falha na tentativa secundária: {e_inner}")
                    print("Se o erro persistir, verifique manualmente o nome do índice UNIQUE na tabela 'instrutores'.")

        except Exception as e:
            db.session.rollback()
            print(f"ERRO CRÍTICO: {e}")

if __name__ == "__main__":
    fix_db_constraint()