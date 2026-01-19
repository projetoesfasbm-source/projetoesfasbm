import sys
import os

# Configuração de caminho para importar o app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from backend.app import create_app
from backend.models.database import db
from backend.models.user import User
from backend.models.aluno import Aluno
from backend.models.user_school import UserSchool

app = create_app()

def deletar_aluno_especifico():
    with app.app_context():
        ALVO_ID = 610
        
        print(f"\n=== REMOÇÃO CIRÚRGICA DE USUÁRIO: ID {ALVO_ID} ===")
        
        # 1. Busca o usuário EXATAMENTE pelo ID
        user = db.session.get(User, ALVO_ID)
        
        if not user:
            print(f"Erro: Usuário com ID {ALVO_ID} não existe no banco.")
            return

        # 2. Mostra os dados para confirmação (Segurança Visual)
        print(f"Usuário Encontrado:")
        print(f" - Nome: {user.nome_completo}")
        print(f" - Matrícula: {user.matricula}")
        print(f" - Role (Papel): {user.role}")
        print(f" - ID: {user.id}")
        
        # Validação extra para garantir que não é o Admin
        if "admin" in user.role or "super" in user.role:
            print("\n[ALERTA] Este usuário parece ter permissões administrativas! O script vai parar por segurança.")
            # Se você tiver certeza absoluta que quer apagar um admin bugado, remova essas 2 linhas abaixo
            return 

        # 3. Executa a exclusão em cascata manual (pra limpar tudo dele)
        try:
            # Remove perfil de aluno
            aluno_profile = Aluno.query.filter_by(user_id=ALVO_ID).first()
            if aluno_profile:
                print(" - Removendo perfil de Aluno...")
                db.session.delete(aluno_profile)
            
            # Remove vínculos de escola
            vinculos = UserSchool.query.filter_by(user_id=ALVO_ID).all()
            for v in vinculos:
                print(f" - Removendo vínculo com escola ID {v.school_id}...")
                db.session.delete(v)
            
            # Remove o Usuário
            print(f" - Removendo Usuário Mestre (ID {ALVO_ID})...")
            db.session.delete(user)
            
            db.session.commit()
            print(f"\nSUCESSO: O usuário ID {ALVO_ID} foi removido completamente.")
            print("O outro usuário (Admin) com a mesma matrícula permanece intacto, pois possui outro ID.")
            
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao deletar: {e}")

if __name__ == "__main__":
    deletar_aluno_especifico()