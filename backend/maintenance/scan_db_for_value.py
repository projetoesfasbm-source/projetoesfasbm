# backend/maintenance/scan_db_for_value.py
import os
import re
import sys
from importlib import import_module

from sqlalchemy import create_engine, MetaData, Table, select, and_, or_, text
from sqlalchemy.sql.sqltypes import String, Unicode, UnicodeText, Text, Integer, BigInteger
from sqlalchemy.exc import SQLAlchemyError

"""
Varredura geral no banco: procura um e-mail e/ou uma ID Func (número) em TODAS as tabelas/colunas.

Como usar:
  source /home/esfasBM/.virtualenvs/meu-ambiente-py313/bin/activate
  cd /home/esfasBM/sistema_escolar_deepseak_1

  # exemplo 1: só email
  python -m backend.maintenance.scan_db_for_value --email claudemir-fernandes@bm.rs.gov.br

  # exemplo 2: só idfunc
  python -m backend.maintenance.scan_db_for_value --idfunc 2277409

  # exemplo 3: ambos
  python -m backend.maintenance.scan_db_for_value --email claudemir-fernandes@bm.rs.gov.br --idfunc 2277409
"""

# -------- utils de app/uri --------

def ensure_project_on_path():
    here = os.path.abspath(os.path.dirname(__file__))            # .../backend/maintenance
    project_root = os.path.abspath(os.path.join(here, "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    return project_root

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
    candidates = [
        "backend.app:create_app",
        "app:create_app",
        "wsgi:app",
        "backend.app:app",
        "app:app",
    ]
    obj = import_first(candidates)
    if obj is None:
        raise RuntimeError("Não localizei a app/factory. Ajuste 'candidates' em build_app().")
    if callable(obj):
        return obj()
    return obj

# -------- normalização --------

def norm_email(v: str | None) -> str | None:
    if not v:
        return None
    return v.strip().lower()

def norm_idfunc(v: str | None) -> str | None:
    if not v:
        return None
    return re.sub(r"\D+", "", v.strip()) or None

# -------- impressão amigável --------

COMMON_COLS = [
    "id","email","id_func","matricula","siape","cpf","usuario_id","escola_id",
    "role","status","is_active","ativo","soft_deleted","created_at","updated_at","nome","nome_completo"
]

def snippet(value, maxlen=80):
    s = str(value)
    if len(s) <= maxlen:
        return s
    return s[:maxlen-3] + "..."

def print_hit(table_name, row, cols, matched_cols):
    pieces = []
    # imprime colunas comuns primeiro
    printed = set()
    for c in COMMON_COLS:
        if c in cols:
            pieces.append(f"{c}={snippet(row[c])!r}")
            printed.add(c)
    # imprime as colunas que deram match (se não estiverem nas comuns)
    for c in matched_cols:
        if c not in printed and c in cols:
            pieces.append(f"{c}~={snippet(row[c])!r}")
            printed.add(c)
    # imprime mais algumas colunas para contexto
    for c in cols:
        if c in printed:
            continue
        if len(printed) >= 12:  # limita para não poluir
            break
        pieces.append(f"{c}={snippet(row[c])!r}")
        printed.add(c)
    print(f"- {table_name}: " + ", ".join(pieces))

# -------- busca --------

def main():
    ensure_project_on_path()

    # parse args
    email = None
    idfunc = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--email" and i + 1 < len(args):
            email = args[i + 1]; i += 2; continue
        if a == "--idfunc" and i + 1 < len(args):
            idfunc = args[i + 1]; i += 2; continue
        i += 1

    email_n = norm_email(email) if email else None
    idfunc_n = norm_idfunc(idfunc) if idfunc else None
    if not email_n and not idfunc_n:
        print("Uso: python -m backend.maintenance.scan_db_for_value --email EMAIL --idfunc 123456")
        sys.exit(1)

    # pega URI do banco da app Flask
    app = build_app()
    with app.app_context():
        uri = app.config.get("SQLALCHEMY_DATABASE_URI")
        if not uri:
            raise RuntimeError("SQLALCHEMY_DATABASE_URI não encontrada na app.")

    engine = create_engine(uri)
    meta = MetaData()
    try:
        meta.reflect(engine)
    except SQLAlchemyError as e:
        print(f"Erro ao refletir metadados do banco: {e}")
        sys.exit(2)

    print("=== SCAN GERAL NO BANCO ===")
    if email_n:  print(f"- Procurando email (case-insensitive, LIKE): {email_n}")
    if idfunc_n: print(f"- Procurando idfunc (dígitos), LIKE: {idfunc_n}")
    print("")

    # pré-classifica tipos textuais
    TEXT_TYPES = (String, Unicode, UnicodeText, Text)
    NUM_TYPES  = (Integer, BigInteger)

    with engine.connect() as conn:
        for table_name, table in meta.tables.items():
            cols = list(table.c.keys())
            matched_any = False

            # constrói condições por coluna
            conds = []
            matched_cols = set()

            for col in table.c:
                coltype = type(col.type)
                colname = col.name.lower()

                # Email: procurar em colunas textuais
                if email_n and issubclass(coltype, TEXT_TYPES):
                    # usa lower() para compatibilidade (SQLite) e ILIKE/LIKE genérico
                    conds.append((col, "email", col.ilike(f"%{email_n}%")))
                    matched_cols.add(col.name)

                # ID Func: procurar em texto (contém a sequência) e, se numérica, igualdade
                if idfunc_n:
                    if issubclass(coltype, TEXT_TYPES):
                        conds.append((col, "idfunc", col.ilike(f"%{idfunc_n}%")))
                        matched_cols.add(col.name)
                    elif issubclass(coltype, NUM_TYPES):
                        # tenta cast “=”
                        try:
                            num_val = int(idfunc_n)
                            conds.append((col, "idfunc", col == num_val))
                            matched_cols.add(col.name)
                        except ValueError:
                            pass

            if not conds:
                continue  # tabela sem colunas compatíveis

            # monta OR de todas as condições desta tabela
            where_or = or_(*[c[2] for c in conds])

            try:
                stmt = select(table).where(where_or).limit(50)
                rows = conn.execute(stmt).fetchall()
                if rows:
                    print(f"[{table_name}] {len(rows)} registro(s):")
                    for row in rows:
                        # identifica em quais colunas bateu (para imprimir com ~=)
                        hit_cols = []
                        for col, tag, expr in conds:
                            try:
                                val = row[col.name]
                                if val is None:
                                    continue
                                sval = str(val)
                                if tag == "email" and email_n and email_n in sval.lower():
                                    hit_cols.append(col.name)
                                if tag == "idfunc" and idfunc_n and idfunc_n in re.sub(r"\D+","", sval):
                                    hit_cols.append(col.name)
                            except Exception:
                                pass
                        print_hit(table_name, row, cols, set(hit_cols))
                    print("")
                    matched_any = True
            except SQLAlchemyError as e:
                print(f"[{table_name}] erro ao consultar: {e}")

    print("=== FIM ===")

if __name__ == "__main__":
    main()