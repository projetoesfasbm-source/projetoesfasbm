# backend/maintenance/list_users.py
import os
import sys
from importlib import import_module
from sqlalchemy import create_engine, MetaData, select

def ensure_project_on_path():
    here = os.path.abspath(os.path.dirname(__file__))
    project_root = os.path.abspath(os.path.join(here, "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

def build_app():
    candidates = [
        "backend.app:create_app", "app:create_app", "wsgi:app",
        "backend.app:app", "app:app",
    ]
    # Simplified import logic for broad compatibility
    for p in candidates:
        try:
            if ":" in p:
                mod, attr = p.split(":", 1)
                m = import_module(mod)
                obj = getattr(m, attr)
                return obj() if callable(obj) else obj
            else:
                obj = import_module(p)
                return obj() if callable(obj) else obj
        except Exception:
            continue
    raise RuntimeError("Não localizei a app/factory.")


def main():
    ensure_project_on_path()
    app = build_app()
    with app.app_context():
        uri = app.config.get("SQLALCHEMY_DATABASE_URI")
        if not uri:
            raise RuntimeError("SQLALCHEMY_DATABASE_URI não encontrada.")
        print(f"DB URI: {uri}\n")

    engine = create_engine(uri)
    meta = MetaData()
    meta.reflect(engine)

    users_table = meta.tables.get("users")
    if users_table is None:
        print("Tabela 'users' não encontrada.")
        return

    print("=== Conteúdo da Tabela 'users' ===")
    with engine.connect() as conn:
        # Mapeia os nomes das colunas para os seus índices
        cols = users_table.c.keys()
        col_map = {name: i for i, name in enumerate(cols)}

        rows = conn.execute(select(users_table)).fetchall()
        if not rows:
            print("Nenhum registo encontrado na tabela 'users'.")
            return

        for i, row in enumerate(rows):
            print(f"--- Registo {i+1} ---")
            for col_name in cols:
                # Acede aos dados pelo índice numérico da coluna
                col_index = col_map[col_name]
                print(f"  {col_name}: {row[col_index]!r}")
            print("")

if __name__ == "__main__":
    main()