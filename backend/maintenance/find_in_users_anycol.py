# backend/maintenance/find_in_users_anycol.py
import os, sys, re
from importlib import import_module
from sqlalchemy import create_engine, MetaData, select, or_
from sqlalchemy.sql.sqltypes import String, Unicode, UnicodeText, Text, Integer, BigInteger

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
        raise RuntimeError("Não localizei a app/factory.")
    return obj() if callable(obj) else obj

def norm_email(v): return (v or "").strip().lower() or None
def norm_idfunc(v): return re.sub(r"\D+","",(v or "").strip()) or None

def main():
    ensure_root()

    email = None
    idfunc = None
    args = sys.argv[1:]
    i=0
    while i < len(args):
        a = args[i]
        if a == "--email" and i+1 < len(args): email = args[i+1]; i+=2; continue
        if a == "--idfunc" and i+1 < len(args): idfunc = args[i+1]; i+=2; continue
        i+=1

    email_n = norm_email(email) if email else None
    idfunc_n = norm_idfunc(idfunc) if idfunc else None
    if not email_n and not idfunc_n:
        print("Uso: python -m backend.maintenance.find_in_users_anycol --email EMAIL --idfunc 123456")
        sys.exit(1)

    app = build_app()
    with app.app_context():
        uri = app.config.get("SQLALCHEMY_DATABASE_URI")
        if not uri: raise RuntimeError("SQLALCHEMY_DATABASE_URI não encontrada.")
        print(f"DB URI: {uri}")

    from sqlalchemy.exc import SQLAlchemyError
    engine = create_engine(uri)
    meta = MetaData()
    meta.reflect(engine)

    users = meta.tables.get("users")
    if users is None:
        print("Tabela 'users' não encontrada.")
        sys.exit(2)

    text_types = (String, Unicode, UnicodeText, Text)
    num_types  = (Integer, BigInteger)

    conds = []
    for col in users.c:
        if email_n and isinstance(col.type, text_types):
            conds.append(col.ilike(f"%{email_n}%"))
        if idfunc_n:
            if isinstance(col.type, text_types):
                conds.append(col.ilike(f"%{idfunc_n}%"))
            elif isinstance(col.type, num_types):
                try:
                    conds.append(col == int(idfunc_n))
                except ValueError:
                    pass

    if not conds:
        print("Nenhuma coluna compatível para busca em 'users'.")
        sys.exit(0)

    with engine.connect() as conn:
        try:
            rows = conn.execute(select(users).where(or_(*conds)).limit(50)).fetchall()
            if not rows:
                print("Nenhum registro correspondente na tabela 'users'.")
                return
            cols = list(users.c.keys())
            print(f"Encontrados {len(rows)} registro(s) em 'users':")
            for r in rows:
                preview = ", ".join([f"{c}={r[c]!r}" for c in cols])
                print(" - " + preview)
        except SQLAlchemyError as e:
            print(f"Erro consultando 'users': {e}")

if __name__ == "__main__":
    main()
