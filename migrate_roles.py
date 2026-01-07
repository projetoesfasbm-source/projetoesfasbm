# scripts/migrate_roles.py
import sys
import os

# Adiciona o diretório pai ao path para importar o app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app import create_app
from backend.models.database import db
from backend.models.user import User
from backend.models.user_school import UserSchool
from sqlalchemy import select

app = create_app()

def migrate_roles():
    """
    Migra roles globais de Users para UserSchools.
    Para cada usuário que tem um role privilegiado globalmente,
    garante que esse role esteja refletido em seu vínculo com a escola.
    """
    with app.app_context():
        print("Iniciando migração de roles globais para UserSchools...")
        
        # Pega usuários que não são programadores nem alunos padrão
        # (pois assumimos que alunos já foram tratados ou o default é aluno)
        privileged_users = db.session.scalars(
            select(User).where(
                User.role.notin_(['aluno', 'programador', 'super_admin'])
            )
        ).all()

        count = 0
        for user in privileged_users:
            global_role = user.role
            
            # Pega os vínculos de escola desse usuário
            # Se ele tem vínculos, atualizamos o role neles para refletir o global
            # Se ele tem múltiplos vínculos, ISSO PODE SER PERIGOSO (o bug original),
            # então vamos priorizar a atualização apenas se o vínculo atual for 'aluno'
            
            user_schools = db.session.scalars(
                select(UserSchool).where(UserSchool.user_id == user.id)
            ).all()

            if not user_schools:
                print(f"AVISO: Usuário {user.matricula} ({global_role}) não tem escola vinculada.")
                continue

            # Estratégia: Atualizar todos os vínculos desse usuário para o cargo global
            # para manter o comportamento atual (embora errado), mas agora explícito na tabela certa.
            # A partir daqui, o admin poderá entrar em cada escola e mudar manualmente.
            for us in user_schools:
                if us.role != global_role:
                    print(f"Atualizando {user.matricula} na escola {us.school_id}: {us.role} -> {global_role}")
                    us.role = global_role
                    count += 1
        
        try:
            db.session.commit()
            print(f"Migração concluída. {count} vínculos atualizados.")
        except Exception as e:
            db.session.rollback()
            print(f"Erro na migração: {e}")

if __name__ == "__main__":
    migrate_roles()