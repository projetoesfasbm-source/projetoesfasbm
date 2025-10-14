# backend/maintenance/fix_super_admin_link.py
import sys
import os

# Adiciona o diretório raiz do projeto ao path do Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import create_app
from backend.models.database import db
from backend.models.user import User
from backend.models.user_school import UserSchool
from sqlalchemy import select, delete

def fix_super_admin_link():
    """
    Encontra o usuário 'super_admin' e remove qualquer vínculo incorreto que ele tenha com escolas.
    """
    print("Iniciando a remoção de vínculos escolares do 'super_admin'...")
    
    app = create_app()
    with app.app_context():
        admin_user = db.session.scalar(
            select(User).where(User.username == 'super_admin')
        )
        
        if not admin_user:
            print("ERRO: Usuário 'super_admin' não encontrado.")
            return

        assignment = db.session.scalar(
            select(UserSchool).where(UserSchool.user_id == admin_user.id)
        )

        if not assignment:
            print("SUCESSO: O usuário 'super_admin' não possui nenhum vínculo escolar. Nenhuma ação foi necessária.")
            return
            
        try:
            print(f"Encontrado vínculo incorreto do 'super_admin' com a escola ID {assignment.school_id}. A remover...")
            
            stmt = delete(UserSchool).where(UserSchool.user_id == admin_user.id)
            db.session.execute(stmt)
            db.session.commit()
            
            print("SUCESSO: O vínculo escolar do 'super_admin' foi removido com sucesso.")
            
        except Exception as e:
            db.session.rollback()
            print(f"ERRO: Ocorreu um erro ao tentar remover o vínculo: {e}")

if __name__ == '__main__':
    fix_super_admin_link()