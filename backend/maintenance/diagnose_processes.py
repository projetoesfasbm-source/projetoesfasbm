# backend/maintenance/diagnose_processes.py

import os
import sys
from sqlalchemy import select

# Adiciona o diretório raiz do projeto ao path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

# Importa os componentes da aplicação
from backend.app import create_app
from backend.models.database import db
from backend.models.processo_disciplina import ProcessoDisciplina
from backend.models.aluno import Aluno
from backend.models.user import User

def diagnose_processes():
    """
    Lista todos os processos disciplinares diretamente do banco de dados,
    mostrando seus campos mais importantes para diagnóstico.
    """
    app = create_app()
    with app.app_context():
        print("\n" + "="*60)
        print("--- INICIANDO DIAGNÓSTICO DIRETO DOS PROCESSOS DISCIPLINARES ---")
        print("="*60)

        try:
            # Busca todos os processos, sem filtros, com os dados do aluno
            todos_processos = db.session.scalars(
                select(ProcessoDisciplina).options(
                    db.joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user)
                ).order_by(ProcessoDisciplina.id)
            ).all()

            if not todos_processos:
                print("\nNenhum processo disciplinar encontrado na tabela.")
                print("="*60)
                return

            print(f"\nEncontrados {len(todos_processos)} registros na tabela 'processos_disciplinares'. Listando todos:\n")

            for p in todos_processos:
                print(f"--- Processo ID: {p.id} ---")
                print(f"  - Aluno:           {p.aluno.user.nome_completo if p.aluno and p.aluno.user else 'N/A'}")
                print(f"  - Fato:            '{p.fato_constatado[:50]}...'")
                print(f"  - Status no DB:    '{p.status}'")
                print(f"  - Decisão Final:   '{p.decisao_final}'")
                print(f"  - Data da Decisão: {p.data_decisao}")
                print("-" * (19 + len(str(p.id))))

        except Exception as e:
            print(f"\nOcorreu um erro ao tentar ler o banco de dados: {e}")

        print("\n" + "="*60)
        print("--- FIM DO DIAGNÓSTICO ---")
        print("="*60 + "\n")


if __name__ == '__main__':
    diagnose_processes()