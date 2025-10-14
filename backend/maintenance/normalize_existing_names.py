# backend/maintenance/normalize_existing_names.py

import os
import sys
from sqlalchemy import select

# Adiciona o diretório raiz do projeto ao path para encontrar os módulos
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

# Importa os componentes da aplicação
from backend.app import create_app
from backend.models.database import db
from backend.models.user import User
from utils.normalizer import normalize_name

def fix_names():
    """
    Itera sobre todos os usuários e aplica a formatação de nome (Title Case)
    para os campos 'nome_completo' e 'nome_de_guerra'.
    """
    print("Iniciando a normalização de nomes de usuários existentes...")
    
    app = create_app()
    with app.app_context():
        users = db.session.scalars(select(User)).all()
        
        if not users:
            print("Nenhum usuário encontrado para verificar.")
            return

        updated_count = 0
        for user in users:
            made_change = False
            
            original_nome_completo = user.nome_completo
            normalized_nome_completo = normalize_name(original_nome_completo)
            if original_nome_completo != normalized_nome_completo:
                user.nome_completo = normalized_nome_completo
                made_change = True
                print(f"  - Corrigindo nome completo do usuário ID {user.id}: '{original_nome_completo}' -> '{normalized_nome_completo}'")

            original_nome_guerra = user.nome_de_guerra
            normalized_nome_guerra = normalize_name(original_nome_guerra)
            if original_nome_guerra != normalized_nome_guerra:
                user.nome_de_guerra = normalized_nome_guerra
                made_change = True
                print(f"  - Corrigindo nome de guerra do usuário ID {user.id}: '{original_nome_guerra}' -> '{normalized_nome_guerra}'")

            if made_change:
                updated_count += 1
        
        if updated_count > 0:
            try:
                db.session.commit()
                print(f"\nSUCESSO: {updated_count} usuário(s) tiveram seus nomes atualizados no banco de dados.")
            except Exception as e:
                db.session.rollback()
                print(f"\nERRO: Ocorreu um erro ao salvar as alterações no banco: {e}")
        else:
            print("\nNenhum nome precisou ser corrigido. Todos os usuários já estão no formato correto.")

if __name__ == '__main__':
    fix_names()