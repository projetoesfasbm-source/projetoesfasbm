# backend/maintenance/reset_process_status.py

import os
import sys
from sqlalchemy import select, update

# Adiciona o diretório raiz do projeto ao path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

# Importa os componentes da aplicação
from backend.app import create_app
from backend.models.database import db
from backend.models.processo_disciplina import ProcessoDisciplina
from backend.models.aluno import Aluno
from backend.models.user import User

def reset_process_status():
    """
    Permite ao administrador resetar o status de processos específicos para 'Pendente'.
    """
    apply_changes = '--apply' in sys.argv
    
    app = create_app()
    with app.app_context():
        print("\n--- FERRAMENTA DE CORREÇÃO DE STATUS DE PROCESSOS ---")
        
        # Pede os IDs dos processos a serem corrigidos
        ids_input = input("Digite os IDs dos processos a serem corrigidos, separados por vírgula (ex: 1,2): ")
        if not ids_input:
            print("Nenhum ID fornecido. Operação cancelada.")
            return

        try:
            ids_to_fix = [int(i.strip()) for i in ids_input.split(',')]
        except ValueError:
            print("ERRO: Por favor, insira apenas números de ID separados por vírgula.")
            return

        # Busca os processos para confirmar
        stmt = (
            select(ProcessoDisciplina)
            .where(ProcessoDisciplina.id.in_(ids_to_fix))
            .options(db.joinedload(ProcessoDisciplina.aluno).joinedload(Aluno.user))
        )
        processes_to_fix = db.session.scalars(stmt).all()

        if not processes_to_fix:
            print("\nNenhum processo encontrado com os IDs fornecidos.")
            return

        print(f"\nOs seguintes {len(processes_to_fix)} processos serão revertidos para o status 'Pendente':")
        for p in processes_to_fix:
            print(f"  - ID: {p.id}, Aluno: {p.aluno.user.nome_completo}, Status Atual: '{p.status}', Decisão: '{p.decisao_final}'")

        if apply_changes:
            print("\n--- APLICANDO CORREÇÃO ---")
            try:
                # Reverte o status e limpa a decisão final
                update_stmt = (
                    update(ProcessoDisciplina)
                    .where(ProcessoDisciplina.id.in_(ids_to_fix))
                    .values(
                        status='Pendente', 
                        decisao_final=None, 
                        data_decisao=None,
                        data_ciente=None,
                        defesa=None,
                        data_defesa=None
                    )
                )
                result = db.session.execute(update_stmt)
                db.session.commit()
                print(f"\nSUCESSO: {result.rowcount} processo(s) foram revertidos para o status 'Pendente'.")
                print("Eles agora aparecerão na aba 'Em Andamento' para serem tratados corretamente.")
            except Exception as e:
                db.session.rollback()
                print(f"\nERRO: Falha ao tentar corrigir os registros: {e}")
        else:
            print("\n--- MODO DE DIAGNÓSTICO (DRY-RUN) ---")
            print("Nenhuma alteração foi feita no banco de dados.")
            print("Para reverter o status desses processos, execute o script novamente com a opção --apply:")
            print(f"python -m backend.maintenance.reset_process_status --apply")


if __name__ == '__main__':
    reset_process_status()