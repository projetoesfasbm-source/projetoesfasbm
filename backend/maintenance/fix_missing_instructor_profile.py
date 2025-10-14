# backend/maintenance/fix_missing_instructor_profile.py
import os
import sys
from importlib import import_module

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
    
    identifier = input("Digite a MATRICULA (Id Func) do instrutor para CORRIGIR: ").strip()
    if not identifier:
        print("Nenhum identificador fornecido. Abortando.")
        return

    app = build_app()
    with app.app_context():
        from backend.models.database import db
        from backend.models.user import User
        from backend.models.instrutor import Instrutor
        from backend.models.user_school import UserSchool
        from sqlalchemy import select

        print("\n--- INICIANDO CORRECAO DE PERFIL ---")
        
        user = db.session.scalar(select(User).where(User.matricula == identifier))

        if not user:
            print(f"\n[ERRO] Nenhum usuario encontrado na tabela 'users' com a matricula '{identifier}'.")
            return
        
        print(f"  - Usuario encontrado: ID {user.id}, Nome: {user.nome_completo}")

        # --- NOVA ETAPA: Encontrar o school_id ---
        school_link = db.session.scalar(select(UserSchool).where(UserSchool.user_id == user.id))
        if not school_link:
            print(f"\n[ERRO] O usuario ID {user.id} nao esta vinculado a nenhuma escola na tabela 'user_schools'. Nao e possivel continuar.")
            return
        
        school_id_to_use = school_link.school_id
        print(f"  - Vinculo de escola encontrado. Usando school_id: {school_id_to_use}")
        # --- FIM DA NOVA ETAPA ---

        instrutor_profile = db.session.scalar(select(Instrutor).where(Instrutor.user_id == user.id))
        
        if instrutor_profile:
            print("  - SUCESSO: O perfil de instrutor para este usuario ja existe. Nenhuma acao necessaria.")
            return

        print("  - PERFIL FALTANDO: Criando novo registro na tabela 'instrutores'...")
        try:
            # Cria a instância e define os atributos, incluindo o school_id obrigatório
            novo_perfil = Instrutor()
            novo_perfil.user_id = user.id
            novo_perfil.school_id = school_id_to_use # <--- CORREÇÃO PRINCIPAL APLICADA
            novo_perfil.telefone = None
            novo_perfil.is_rr = False

            db.session.add(novo_perfil)
            db.session.commit()
            print("\n[RESULTADO] SUCESSO! O perfil de instrutor foi criado e vinculado ao usuario e a escola correta.")
            print("O instrutor agora deve aparecer corretamente nas listagens do sistema.")

        except Exception as e:
            db.session.rollback()
            print(f"\n[ERRO] Ocorreu um erro ao tentar criar o perfil: {e}")

        print("\n--- FIM DA CORRECAO ---")

if __name__ == "__main__":
    main()