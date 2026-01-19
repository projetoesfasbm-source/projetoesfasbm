# backend/maintenance/fix_turma_constraint_production.py
import sys
import os
from sqlalchemy import text

# Adiciona o diretório raiz ao path para importar o app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from backend.app import create_app
from backend.models.database import db

app = create_app()

def fix_turma_constraints():
    with app.app_context():
        print("--- INICIANDO CORREÇÃO DE UNICIDADE DA TABELA TURMAS ---")
        
        # 1. Descobrir o nome da constraint UNIQUE atual no campo 'nome'
        try:
            # Tenta pegar o nome da chave única. No MySQL geralmente é 'nome' ou 'nome_2' se foi criado via SQLAlchemy
            inspector = db.inspect(db.engine)
            constraints = inspector.get_unique_constraints('turmas')
            
            constraint_name_to_drop = None
            for c in constraints:
                # Procura a constraint que afeta APENAS a coluna 'nome'
                if c['column_names'] == ['nome']:
                    constraint_name_to_drop = c['name']
                    break
            
            if constraint_name_to_drop:
                print(f"Constraint global encontrada: '{constraint_name_to_drop}'. Removendo...")
                db.session.execute(text(f"ALTER TABLE turmas DROP INDEX {constraint_name_to_drop}"))
                print("Constraint global removida com sucesso.")
            else:
                print("Nenhuma constraint global exclusiva para 'nome' foi encontrada. Talvez já tenha sido removida.")

        except Exception as e:
            print(f"Aviso ao tentar remover constraint antiga: {e}")

        # 2. Criar a nova constraint composta (nome + school_id)
        try:
            print("Criando nova constraint composta (nome + school_id)...")
            # Verifica se já existe para não dar erro
            constraints_new = inspector.get_unique_constraints('turmas')
            exists = any(c['name'] == 'uq_turma_nome_escola' for c in constraints_new)
            
            if not exists:
                db.session.execute(text("ALTER TABLE turmas ADD CONSTRAINT uq_turma_nome_escola UNIQUE (nome, school_id)"))
                print("Nova constraint 'uq_turma_nome_escola' criada com sucesso!")
            else:
                print("A constraint 'uq_turma_nome_escola' já existe.")
                
        except Exception as e:
            print(f"Erro ao criar nova constraint: {e}")
            # Se falhar aqui, pode ser que já existam duplicatas PERFEITAS (mesmo nome e mesma escola).
            # Nesse caso, o admin terá que renomear manualmente antes.

        db.session.commit()
        print("--- PROCESSO CONCLUÍDO ---")

if __name__ == "__main__":
    fix_turma_constraints()