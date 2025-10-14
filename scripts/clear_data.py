import sys
import os
from sqlalchemy import select

# Adiciona o diretório raiz do projeto ao path do Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importa os modelos do banco de dados
from backend.models.database import db
from backend.models.user import User
from backend.models.aluno import Aluno
from backend.models.instrutor import Instrutor
from backend.models.turma import Turma
from backend.models.disciplina import Disciplina
from backend.models.horario import Horario
from backend.models.historico_disciplina import HistoricoDisciplina
from backend.models.historico import HistoricoAluno
from backend.models.disciplina_turma import DisciplinaTurma
from backend.models.turma_cargo import TurmaCargo
from backend.models.user_school import UserSchool

def clear_transactional_data():
    """
    Apaga todos os dados transacionais do banco, mas preserva a estrutura
    e os usuários/escolas essenciais para o funcionamento do sistema.
    """
    print("Iniciando a limpeza dos dados da aplicação...")

    # A ordem de exclusão é importante para respeitar as chaves estrangeiras
    tables_to_clear = [
        Horario, HistoricoDisciplina, HistoricoAluno, DisciplinaTurma, TurmaCargo,
        Aluno, Instrutor, Turma, Disciplina, UserSchool
    ]
    
    try:
        for table in tables_to_clear:
            deleted_rows = db.session.query(table).delete()
            print(f"  - {deleted_rows} registros apagados de '{table.__tablename__}'.")
        
        # Apaga apenas os usuários que não são essenciais
        deleted_users = db.session.query(User).filter(
            User.role.notin_(['super_admin', 'programador'])
        ).delete()
        print(f"  - {deleted_users} usuários não essenciais apagados.")

        db.session.commit()
        print("\nSucesso! Os dados foram limpos, mantendo a estrutura e os administradores.")
    except Exception as e:
        db.session.rollback()
        print(f"\nOcorreu um erro durante a limpeza: {e}")