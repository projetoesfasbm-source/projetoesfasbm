# backend/maintenance/fix_inconsistent_processes.py

import os
import sys
from sqlalchemy import select, update

# Adiciona o diretório raiz do projeto ao path para encontrar os módulos
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

# Importa os componentes da aplicação
from backend.app import create_app
from backend.models.database import db
from backend.models.processo_disciplina import ProcessoDisciplina
from backend.models.aluno import Aluno
from backend.models.user import User

def fix_inconsistent_processes():
    """
    Encontra processos marcados como 'Finalizado' mas sem uma decisão final
    e reverte o status para 'Defesa Enviada' para que possam ser finalizados corretamente.
    """
    apply_changes = '--apply' in sys.argv
    
    app = create_app()
    with app.app_context():
        print("Iniciando a verificação de processos inconsistentes...")

        # Encontra processos onde o status é 'Finalizado', mas a decisão é nula ou vazia.
        stmt = (
            select(ProcessoDisciplina)
            .where(
                ProcessoDisciplina.status == 'Finalizado',
                (ProcessoDisciplina.decisao_final.is_(None) | (ProcessoDisciplina.decisao_final == ''))
            )
            .options(db.joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user))
        )
        
        inconsistent_processes = db.session.scalars(stmt).all()
        
        if not inconsistent_processes:
            print("\nNenhum processo inconsistente encontrado. O banco de dados está correto!")
            return

        print(f"\nEncontrados {len(inconsistent_processes)} processos marcados como 'Finalizado' sem uma decisão final:")
        ids_to_fix = []
        for p in inconsistent_processes:
            ids_to_fix.append(p.id)
            print(f"  - ID: {p.id}, Aluno: {p.aluno.user.nome_completo}, Fato: '{p.fato_constatado[:50]}...'")

        if apply_changes:
            print("\n--- APLICANDO CORREÇÃO ---")
            try:
                update_stmt = (
                    update(ProcessoDisciplina)
                    .where(ProcessoDisciplina.id.in_(ids_to_fix))
                    .values(status='Defesa Enviada')
                )
                result = db.session.execute(update_stmt)
                db.session.commit()
                print(f"\nSUCESSO: {result.rowcount} processo(s) inconsistente(s) foram revertidos para o status 'Defesa Enviada'.")
                print("Agora você pode finalizá-los corretamente na interface do sistema.")
            except Exception as e:
                db.session.rollback()
                print(f"\nERRO: Falha ao tentar corrigir os registros: {e}")
        else:
            print("\n--- MODO DE DIAGNÓSTICO (DRY-RUN) ---")
            print("Nenhuma alteração foi feita no banco de dados.")
            print("Para reverter o status desses processos para 'Defesa Enviada', execute o script novamente com a opção --apply:")
            print("python -m backend.maintenance.fix_inconsistent_processes --apply")


if __name__ == '__main__':
    fix_inconsistent_processes()