# backend/maintenance/fix_super_admin_role.py
import sys
import os

# Adiciona o diretório raiz do projeto ao path do Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import create_app
from backend.models.database import db
from backend.models.user import User
from sqlalchemy import select

def fix_super_admin_role():
    """
    Encontra o usuário 'super_admin' e garante que seu papel principal na tabela de usuários seja 'super_admin'.
    """
    print("Iniciando a correção do papel do usuário 'super_admin'...")
    
    app = create_app()
    with app.app_context():
        # Encontra o usuário 'super_admin'
        admin_user = db.session.scalar(
            select(User).where(User.username == 'super_admin')
        )
        
        if not admin_user:
            print("ERRO: Usuário 'super_admin' não foi encontrado. Nenhuma ação foi tomada.")
            return

        if admin_user.role == 'super_admin':
            print("SUCESSO: O papel do usuário 'super_admin' já está correto.")
            return
            
        try:
            print(f"Encontrado papel incorreto '{admin_user.role}'. A corrigir para 'super_admin'...")
            admin_user.role = 'super_admin'
            db.session.commit()
            print("SUCESSO: O papel do usuário 'super_admin' foi corrigido com sucesso na tabela principal.")
            
        except Exception as e:
            db.session.rollback()
            print(f"ERRO: Ocorreu um erro ao tentar corrigir o papel: {e}")

if __name__ == '__main__':
    fix_super_admin_role()