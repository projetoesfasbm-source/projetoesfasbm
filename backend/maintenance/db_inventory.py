# backend/maintenance/db_inventory.py
import os
import re
import sys
from importlib import import_module
from sqlalchemy import create_engine, MetaData, select, func, or_, and_
from sqlalchemy.sql.sqltypes import String, Unicode, UnicodeText, Text, Integer, BigInteger
from sqlalchemy.exc import SQLAlchemyError

def ensure_project_on_path():
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
    cand = ["backend.app:create_app","app:create_app","wsgi:app","backend.app:app","app:app"]
    obj = import_first(cand)
    if obj is None:
        raise RuntimeError("Não localizei a app/factory. Ajuste candidatos em build_app().")
    return obj() if callable(obj) else obj

def norm_email(v): return (v or "").strip().lower() or None
def norm_idfunc(v): return re.sub(r"\D+","",(v or "").strip()) or None

def main():
    ensure_project_on_path()

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

    app = build_app()
    with app.app_context():
        uri = app.config.get("SQLALCHEMY_DATABASE_URI")
        if not uri: raise RuntimeError("SQLALCHEMY_DATABASE_URI não encontrada.")
        print(f"DB URI: {uri}")

    engine = create_engine(uri)
    meta = MetaData()
    meta.reflect(engine)

    print("\n=== TABELAS E CONTAGENS ===")
    with engine.connect() as conn:
        for name, table in meta.tables.items():
            try:
                stmt = select(func.count()).select_from(table)
                count = conn.execute(stmt).scalar()
            except SQLAlchemyError:
                count = "erro"
            print(f"- {name}: {count}")

    if not email_n and not idfunc_n:
        print("\n(use --email e/ou --idfunc para procurar valores em colunas relevantes)")
        return

    print("\n=== PROCURANDO VALORES EM COLUNAS RELEVANTES ===")
    RELEVANT_SUBSTR = ["email","mail","idfunc","id_func","matricula","siape","cpf","documento"]
    with engine.connect() as conn:
        for name, table in meta.tables.items():
            cols = list(table.c.keys())
            candidates = [c for c in table.c if any(s in c.name.lower() for s in RELEVANT_SUBSTR)]
            if not candidates:
                continue

            conditions = []
            for c in candidates:
                if isinstance(c.type, (String, Unicode, UnicodeText, Text)):
                    if email_n:
                        conditions.append(c.ilike(f"%{email_n}%"))
                    if idfunc_n:
                        conditions.append(c.ilike(f"%{idfunc_n}%"))
                if idfunc_n and isinstance(c.type, (Integer, BigInteger)):
                    try:
                        num = int(idfunc_n)
                        conditions.append(c == num)
                    except ValueError:
                        pass

            if not conditions:
                continue

            where = or_(*conditions)
            try:
                rows = conn.execute(select(table).where(where).limit(50)).fetchall()
                if rows:
                    print(f"[{name}] {len(rows)} registro(s) batendo)")
                    for r in rows:
                        preview = ", ".join([f"{c}={r[c]!r}" for c in cols[:12]])
                        print(" - " + preview[:300])
            except SQLAlchemyError as e:
                print(f"[{name}] erro ao consultar: {e}")

if __name__ == "__main__":
    main()