# backend/maintenance/cleanup_orphan_disciplines.py

import os
import sys

# Adiciona o diretório raiz do projeto ao path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

# Importa os componentes da aplicação
from backend.app import create_app
from backend.models.database import db
from backend.models.disciplina import Disciplina
from backend.models.horario import Horario
from backend.models.disciplina_turma import DisciplinaTurma
from backend.models.historico_disciplina import HistoricoDisciplina

def cleanup_orphan_disciplines():
    """
    Limpa disciplinas e todos os seus dados associados para permitir a migração
    que vincula disciplinas a turmas.
    """
    app = create_app()
    with app.app_context():
        print("\n--- INICIANDO LIMPEZA DE DISCIPLINAS ÓRFÃS ---")
        
        try:
            # A ordem é importante para respeitar as chaves estrangeiras
            print("Limpando horários agendados...")
            db.session.query(Horario).delete()
            
            print("Limpando vínculos de instrutores (disciplina_turmas)...")
            db.session.query(DisciplinaTurma).delete()
            
            print("Limpando histórico de notas dos alunos (historico_disciplinas)...")
            db.session.query(HistoricoDisciplina).delete()
            
            print("Limpando a tabela de disciplinas...")
            num_deleted = db.session.query(Disciplina).delete()
            
            db.session.commit()
            
            print(f"\nSUCESSO: {num_deleted} disciplinas e todos os seus dados associados foram removidos.")
            print("O banco de dados está pronto para a migração.")

        except Exception as e:
            db.session.rollback()
            print(f"\nERRO: Ocorreu um erro durante a limpeza: {e}")
            print("Nenhuma alteração foi salva no banco de dados.")

        print("--- FIM DA LIMPEZA ---\n")


if __name__ == '__main__':
    cleanup_orphan_disciplines()