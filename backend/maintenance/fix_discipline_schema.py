# backend/maintenance/fix_discipline_schema.py

import os
import sys

# Adiciona o diretório raiz do projeto ao path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

# Importa os componentes da aplicação
from backend.app import create_app
from backend.models.database import db

def fix_discipline_schema():
    """
    Força a remoção de colunas e constraints inconsistentes da tabela 'disciplinas'
    para permitir que a migração seja executada corretamente.
    """
    app = create_app()
    with app.app_context():
        print("\n--- FERRAMENTA DE REPARO DE SCHEMA DA TABELA 'DISCIPLINAS' (v2) ---")
        
        with db.engine.connect() as connection:
            trans = connection.begin()
            try:
                print("Verificando constraints existentes na tabela 'disciplinas'...")
                
                # Busca todas as constraints (foreign key e unique) associadas à tabela
                constraints_result = connection.execute(db.text(
                    "SELECT CONSTRAINT_NAME, CONSTRAINT_TYPE FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'disciplinas';"
                ))
                
                for row in constraints_result.mappings():
                    constraint_name = row['CONSTRAINT_NAME']
                    constraint_type = row['CONSTRAINT_TYPE']
                    
                    if constraint_name == 'PRIMARY':
                        continue # Nunca remove a chave primária

                    print(f"  - Encontrada constraint '{constraint_name}' do tipo '{constraint_type}'. Tentando remover...")
                    
                    try:
                        if constraint_type == 'FOREIGN KEY':
                            connection.execute(db.text(f"ALTER TABLE disciplinas DROP FOREIGN KEY `{constraint_name}`;"))
                            print(f"    - Constraint FOREIGN KEY '{constraint_name}' removida com sucesso.")
                        elif constraint_type == 'UNIQUE':
                            connection.execute(db.text(f"ALTER TABLE disciplinas DROP INDEX `{constraint_name}`;"))
                            print(f"    - Constraint UNIQUE '{constraint_name}' removida com sucesso.")
                    except Exception as e:
                        print(f"    - Aviso: Não foi possível remover a constraint '{constraint_name}'. Erro: {e}. Continuando...")


                print("\nVerificando colunas inconsistentes...")
                # Verifica se a coluna 'turma_id' existe antes de tentar removê-la
                result = connection.execute(db.text(
                    "SHOW COLUMNS FROM disciplinas LIKE 'turma_id';"
                ))
                if result.fetchone():
                    print("  - Coluna 'turma_id' encontrada. Removendo...")
                    connection.execute(db.text("ALTER TABLE disciplinas DROP COLUMN turma_id;"))
                    print("  - Coluna 'turma_id' removida com sucesso.")
                else:
                    print("  - Coluna 'turma_id' não encontrada. Nenhuma ação necessária.")

                trans.commit()
                print("\n[SUCESSO] O schema da tabela 'disciplinas' foi limpo e está pronto para a migração.")

            except Exception as e:
                trans.rollback()
                print(f"\n[ERRO] Ocorreu um erro durante o reparo do schema: {e}")
                print("Nenhuma alteração foi salva. Verifique o erro acima.")

        print("--- FIM DO REPARO ---\n")


if __name__ == '__main__':
    fix_discipline_schema()