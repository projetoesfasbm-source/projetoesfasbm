# backend/maintenance/force_recreate_disciplinas.py

import os
import sys
from sqlalchemy import text

# Adiciona o diretório raiz do projeto ao path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

# Importa os componentes da aplicação
from backend.app import create_app
from backend.models.database import db

def force_recreate_table():
    """
    Força a recriação da tabela 'disciplinas' com a nova estrutura correta,
    ignorando o estado inconsistente do Alembic.
    """
    app = create_app()
    with app.app_context():
        print("\n--- FERRAMENTA DE RECRIAÇÃO FORÇADA DA TABELA 'DISCIPLINAS' ---")
        
        with db.engine.connect() as connection:
            trans = connection.begin()
            try:
                confirm = input(
                    "AVISO: Esta operação irá apagar permanentemente a tabela 'disciplinas' "
                    "e todos os seus dados (horários, vínculos, histórico de notas).\n"
                    "Esta é a solução definitiva para o erro de migração. Deseja continuar? (s/n): "
                ).lower()
                if confirm != 's':
                    print("Operação cancelada.")
                    trans.rollback()
                    return

                print("\n[PASSO 1/2] Removendo a tabela 'disciplinas' existente (se houver)...")
                connection.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
                connection.execute(text("DROP TABLE IF EXISTS disciplinas;"))
                print("  - Tabela 'disciplinas' antiga removida.")

                print("\n[PASSO 2/2] Recriando a tabela 'disciplinas' com a nova estrutura...")
                connection.execute(text("""
                    CREATE TABLE disciplinas (
                        id INTEGER NOT NULL AUTO_INCREMENT,
                        materia VARCHAR(100) NOT NULL,
                        carga_horaria_prevista INTEGER NOT NULL,
                        carga_horaria_cumprida INTEGER NOT NULL,
                        created_at DATETIME NOT NULL,
                        turma_id INTEGER NOT NULL,
                        ciclo_id INTEGER NOT NULL,
                        PRIMARY KEY (id),
                        UNIQUE KEY _materia_turma_uc (materia, turma_id),
                        FOREIGN KEY(ciclo_id) REFERENCES ciclos (id),
                        FOREIGN KEY(turma_id) REFERENCES turmas (id)
                    )
                """))
                connection.execute(text("SET FOREIGN_KEY_CHECKS=1;"))
                print("  - Tabela 'disciplinas' recriada com sucesso.")
                
                trans.commit()
                
                print("\n[SUCESSO] A tabela foi recriada. O banco de dados agora está alinhado com a nova estrutura.")
                print("O próximo passo é 'estampar' a migração para finalizar o processo.")

            except Exception as e:
                trans.rollback()
                print(f"\n[ERRO] Ocorreu um erro durante a operação: {e}")
                print("Nenhuma alteração foi salva no banco de dados.")

        print("--- FIM DA OPERAÇÃO ---\n")


if __name__ == '__main__':
    force_recreate_table()