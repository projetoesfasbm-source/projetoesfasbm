# backend/maintenance/fix_programmer_role.py
import os
import sys
from importlib import import_module
from sqlalchemy import create_engine, select, update

# Adiciona o diretório raiz do projeto ao path do Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models.database import db
from backend.models.user import User
from backend.app import create_app

def fix_role():
    """
    Encontra o usuário 'programador' e garante que sua role seja 'programador'.
    """
    print("Iniciando a correção da função do usuário 'programador'...")
    
    # Encontra o usuário pelo username, que é único
    prog_user = db.session.scalar(
        select(User).where(User.username == 'programador')
    )
    
    if not prog_user:
        print("ERRO: Usuário 'programador' não encontrado na base de dados.")
        return

    if prog_user.role == 'programador':
        print("SUCESSO: A função do usuário 'programador' já está correta.")
    else:
        print(f"A função atual é '{prog_user.role}'. A corrigir para 'programador'...")
        prog_user.role = 'programador'
        db.session.commit()
        print("SUCESSO: A função do usuário 'programador' foi corrigida.")

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        fix_role()