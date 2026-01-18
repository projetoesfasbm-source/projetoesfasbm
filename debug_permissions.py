import sys
import os
sys.path.append(os.getcwd())
from backend.app import create_app
from backend.models.database import db
from backend.models.user import User
from backend.services.user_service import UserService

app = create_app()

def check_permissions():
    with app.app_context():
        print("=== DIAGNÓSTICO DE PERMISSÕES E MENU ===")
        # Tente pegar o primeiro usuário admin ou o seu usuário específico se souber a matricula
        user = db.session.scalars(select(User).limit(1)).first()
        
        if not user:
            print("❌ Nenhum usuário encontrado no banco.")
            return

        print(f"Usuário Teste: {user.nome_completo} ({user.role})")
        
        # Simula o que o base.html geralmente verifica
        school_id = UserService.get_current_school_id() # Pode ser None fora de request web
        print(f"School ID Atual (Sessão): {school_id}")
        
        if hasattr(user, 'is_admin'):
            print(f"Is Admin? {user.is_admin}")
        
        # Verifica relacionamentos críticos
        if user.role == 'aluno':
            if user.aluno_profile:
                print(f"✅ Perfil Aluno OK. Turma ID: {user.aluno_profile.turma_id}")
            else:
                print("❌ ERRO: Usuário é aluno mas sem 'aluno_profile'.")

if __name__ == "__main__":
    from sqlalchemy import select
    check_permissions()