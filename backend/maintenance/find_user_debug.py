# backend/maintenance/find_user_debug.py
import sys
import os
from sqlalchemy import select

# Setup do ambiente Flask
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from backend.app import create_app
from backend.models.database import db
from backend.models.user import User

def find_user_by_name(partial_name):
    app = create_app()
    with app.app_context():
        print(f"--- Buscando usuários com nome contendo: '{partial_name}' ---")
        users = db.session.scalars(
            select(User).where(User.nome_completo.ilike(f"%{partial_name}%"))
        ).all()

        if not users:
            print("Nenhum usuário encontrado com esse nome.")
            return

        for u in users:
            print(f"ID: {u.id} | Matrícula: '{u.matricula}' | Username: '{u.username}' | Nome: {u.nome_completo}")

if __name__ == "__main__":
    name_query = "Mateus"
    if len(sys.argv) > 1:
        name_query = sys.argv[1]
    find_user_by_name(name_query)