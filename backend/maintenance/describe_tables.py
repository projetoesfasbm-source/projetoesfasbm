# backend/maintenance/describe_tables.py
import os, sys
from importlib import import_module
from sqlalchemy import create_engine, MetaData

TARGETS = ["users", "user_schools", "pre_cadastros", "instrutores", "alunos"]

def ensure_root():
    here = os.path.abspath(os.path.dirname(__file__))
    root = os.path.abspath(os.path.join(here, "..", ".."))
    if root not in sys.path:
        sys.path.insert(0, root)
    return root

def import_first(paths):
    for p in paths:
        try:
            if ":" in p:
                mod, attr = p.split(":", 1)
                m = import_module(mod)
                return getattr(m, attr)
            else:
                return import_module(p)
        except Exception:
            continue
    return None

def build_app():
    cand = ["backend.app:create_app", "app:create_app", "wsgi:app", "backend.app:app", "app:app"]
    obj = import_first(cand)
    if obj is None:
        raise RuntimeError("Não localizei a app/factory. Ajuste a lista em build_app().")
    return obj() if callable(obj) else obj

def main():
    ensure_root()
    app = build_app()
    with app.app_context():
        uri = app.config.get("SQLALCHEMY_DATABASE_URI")
        if not uri:
            raise RuntimeError("SQLALCHEMY_DATABASE_URI não encontrada.")
        print(f"DB URI: {uri}")

    engine = create_engine(uri)
    meta = MetaData()
    meta.reflect(engine)

    print("\n=== DESCRIÇÃO DE TABELAS ===")
    for name in TARGETS:
        tbl = meta.tables.get(name)
        if tbl is None:
            print(f"- {name}: (não existe)")
            continue
        print(f"- {name}:")
        for c in tbl.c:
            pk = " [PK]" if c.primary_key else ""
            print(f"  • {c.name}  ({c.type}){pk}")
        print("")
    print("=== FIM ===")

if __name__ == "__main__":
    main()