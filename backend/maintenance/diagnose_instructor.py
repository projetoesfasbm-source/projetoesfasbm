# backend/maintenance/diagnose_instructor.py
import os
import sys
from importlib import import_module
from sqlalchemy import create_engine, select

def ensure_project_on_path():
    here = os.path.abspath(os.path.dirname(__file__))
    project_root = os.path.abspath(os.path.join(here, "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

def build_app():
    candidates = ["backend.app:create_app", "app:create_app"]
    for p in candidates:
        try:
            mod, attr = p.split(":", 1)
            m = import_module(mod)
            obj = getattr(m, attr)
            return obj() if callable(obj) else obj
        except Exception:
            continue
    raise RuntimeError("Nao foi possivel localizar a app factory.")

def main():
    ensure_project_on_path()
    
    identifier = input("Digite a MATRICULA (Id Func) ou o EMAIL do instrutor para diagnosticar: ").strip()
    if not identifier:
        print("Nenhum identificador fornecido. Abortando.")
        return

    app = build_app()
    with app.app_context():
        from backend.models.database import db
        from backend.models.user import User
        from backend.models.instrutor import Instrutor
        from backend.models.user_school import UserSchool

        print("\n--- INICIANDO DIAGNOSTICO ---")
        
        # 1. Procurar na tabela 'users'
        print(f"\n1. Procurando usuario com '{identifier}' na tabela 'users'...")
        query = select(User).where(
            (User.matricula == identifier) | (User.email == identifier)
        )
        user = db.session.scalar(query)

        if not user:
            print("\n[RESULTADO] FALHA: Nenhum usuario encontrado na tabela 'users' com essa matricula ou email.")
            print("--- FIM DO DIAGNOSTICO ---")
            return
        
        print(f"  - SUCESSO: Usuario encontrado! ID: {user.id}, Nome: {user.nome_completo}, Role: '{user.role}', Ativo: {user.is_active}")

        if user.role != 'instrutor':
            print(f"  - ATENCAO: O papel (role) deste usuario e '{user.role}', mas deveria ser 'instrutor'.")

        # 2. Procurar na tabela 'instrutores'
        print(f"\n2. Verificando perfil na tabela 'instrutores' com user_id = {user.id}...")
        instrutor_profile = db.session.scalar(select(Instrutor).where(Instrutor.user_id == user.id))
        
        if not instrutor_profile:
            print(f"  - FALHA: Nao foi encontrado um perfil de instrutor correspondente para este usuario.")
            print("    > Causa provavel: O registro na tabela 'instrutores' nao foi criado.")
        else:
            print(f"  - SUCESSO: Perfil de instrutor encontrado! ID do Instrutor: {instrutor_profile.id}")

        # 3. Procurar na tabela 'user_schools'
        print(f"\n3. Verificando vinculo com a escola na tabela 'user_schools'...")
        school_links = db.session.scalars(select(UserSchool).where(UserSchool.user_id == user.id)).all()

        if not school_links:
            print(f"  - FALHA: O usuario nao esta vinculado a NENHUMA escola.")
            print("    > Causa provavel: O registro na tabela 'user_schools' nao foi criado.")
        else:
            print(f"  - SUCESSO: Usuario vinculado a {len(school_links)} escola(s):")
            for link in school_links:
                print(f"    - Escola ID: {link.school_id}, com o papel '{link.role}'")
                if link.role != 'instrutor':
                    print(f"      - ATENCAO: O papel do vinculo e '{link.role}', mas deveria ser 'instrutor'.")

        print("\n--- FIM DO DIAGNOSTICO ---")
        print("\nAnalise os resultados acima para identificar a falha.")
        if not instrutor_profile:
             print("Acao recomendada: Criar manualmente o registro na tabela 'instrutores'.")
        if not school_links:
             print("Acao recomendada: Criar manualmente o vinculo na tabela 'user_schools' (Super Admin -> Gerenciar Atribuicoes).")


if __name__ == "__main__":
    main()