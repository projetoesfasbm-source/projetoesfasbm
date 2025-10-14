# backend/maintenance/fix_programmer_link.py
import sys
import os

# Adiciona o diretório raiz do projeto ao path do Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import create_app
from backend.models.database import db
from backend.models.user import User
from backend.models.user_school import UserSchool
from sqlalchemy import select, delete

def fix_programmer_link():
    """
    Encontra o usuário 'programador' e remove qualquer vínculo incorreto
    que ele tenha com escolas na tabela user_schools.
    """
    print("Iniciando a correção de vínculo do usuário 'programador'...")
    
    # Encontra o usuário 'programador'
    prog_user = db.session.scalar(
        select(User).where(User.username == 'programador')
    )
    
    if not prog_user:
        print("ERRO: Usuário 'programador' não foi encontrado. Nenhuma ação foi tomada.")
        return

    # Procura por vínculos na tabela user_schools
    assignment = db.session.scalar(
        select(UserSchool).where(UserSchool.user_id == prog_user.id)
    )

    if not assignment:
        print("SUCESSO: O usuário 'programador' não possui nenhum vínculo escolar. Nenhuma ação foi necessária.")
        return
        
    try:
        print(f"Encontrado vínculo incorreto do usuário 'programador' com a escola ID {assignment.school_id}. A remover...")
        
        # Apaga o vínculo incorreto
        stmt = delete(UserSchool).where(UserSchool.user_id == prog_user.id)
        db.session.execute(stmt)
        db.session.commit()
        
        print("SUCESSO: O vínculo escolar do usuário 'programador' foi removido com sucesso.")
        print("O usuário 'programador' foi restaurado ao seu estado global.")
        
    except Exception as e:
        db.session.rollback()
        print(f"ERRO: Ocorreu um erro ao tentar remover o vínculo: {e}")


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        fix_programmer_link()