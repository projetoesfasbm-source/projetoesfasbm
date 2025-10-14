# backend/maintenance/find_user_conflicts.py
import os
import re
import sys
from importlib import import_module

from sqlalchemy import create_engine, MetaData, select, and_
from sqlalchemy.exc import SQLAlchemyError

"""
Diagnóstico de “registro fantasma” para e-mail e/ou ID Func,
sem depender de importar o objeto `db` do projeto.

COMO USAR:
  # ative o venv correto
  source /home/esfasBM/.virtualenvs/meu-ambiente-py313/bin/activate

  # vá para a raiz do projeto
  cd /home/esfasBM/sistema_escolar_deepseak_1

  # execute com seu e-mail e/ou idfunc (use UM valor após --idfunc)
  python -m backend.maintenance.find_user_conflicts --email fulano@bm.rs.gov.br
  python -m backend.maintenance.find_user_conflicts --idfunc 2277409
  python -m backend.maintenance.find_user_conflicts --email fulano@bm.rs.gov.br --idfunc 2277409
"""

# ---------- utilidades de caminho/app ----------

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
    """
    Descobre sua app Flask ou factory sem depender do `db`.
    Ajuste a lista se sua app estiver em outro módulo.
    """
    candidates = [
        "backend.app:create_app",
        "app:create_app",
        "wsgi:app",
        "backend.app:app",
        "app:app",
    ]
    obj = import_first(candidates)
    if obj is None:
        raise RuntimeError(
            "Não localizei a app/factory. Ajuste a lista 'candidates' em build_app()."
        )
    if callable(obj):
        return obj()
    return obj  # já é a app

# ---------- normalização simples ----------

def norm_email(v: str | None) -> str | None:
    if not v:
        return None
    return v.strip().lower()

def norm_idfunc(v: str | None) -> str | None:
    if not v:
        return None
    return re.sub(r"\D+", "", v.strip()) or None

# ---------- consulta genérica refletindo as tabelas ----------

TABLE_CANDIDATES = [
    # nome prováveis das tabelas (ajuste aqui se seu schema usa outros nomes)
    "usuarios",
    "users",
    "instrutores",
    "alunos",
    "pre_cadastros",
    "precadastros",
    "usuarios_orfaos",
    "usuarios_orfãos",
]

COLUMNS_OF_INTEREST = [
    "id", "email", "id_func", "role", "is_active", "soft_deleted",
    "status", "escola_id", "usuario_id", "ativo", "created_at",
]

def build_filters(table, email_n, idfunc_n):
    filters = []
    cols = table.c.keys()

    if email_n and "email" in cols:
        filters.append(table.c.email == email_n)
    if idfunc_n and "id_func" in cols:
        filters.append(table.c.id_func == idfunc_n)

    # Se nenhum filtro aplicável existir, evita SELECT FULL TABLE
    if not filters:
        return None
    return and_(*filters) if len(filters) > 1 else filters[0]

def print_rows(title, rows, cols):
    if not rows:
        return
    print(f"[{title}] {len(rows)} registro(s):")
    for r in rows:
        pieces = []
        for c in COLUMNS_OF_INTEREST:
            if c in cols:
                pieces.append(f"{c}={getattr(r, c)!r}")
        print(" - " + ", ".join(pieces))
    print("")

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
            email = args[i + 1]
            i += 2
            continue
        if a == "--idfunc" and i + 1 < len(args):
            idfunc = args[i + 1]
            i += 2
            continue
        i += 1

    email_n = norm_email(email) if email else None
    idfunc_n = norm_idfunc(idfunc) if idfunc else None

    if not email_n and not idfunc_n:
        print("Uso: python -m backend.maintenance.find_user_conflicts --email EMAIL --idfunc 123456")
        sys.exit(1)

    # carrega app só para ler a URI do banco
    app = build_app()
    with app.app_context():
        uri = app.config.get("SQLALCHEMY_DATABASE_URI")
        if not uri:
            raise RuntimeError("Config 'SQLALCHEMY_DATABASE_URI' não encontrada na app.")

    # conecta direto via SQLAlchemy Core
    engine = create_engine(uri)
    meta = MetaData()
    try:
        meta.reflect(engine)
    except SQLAlchemyError as e:
        print(f"Erro ao refletir metadados do banco: {e}")
        sys.exit(2)

    # mapeia nomes reais disponíveis
    available = {name: meta.tables[name] for name in meta.tables.keys()}

    print("=== PROCURANDO CONFLITOS ===")
    if email_n:
        print(f"- Email (normalizado): {email_n}")
    if idfunc_n:
        print(f"- ID Func (normalizado): {idfunc_n}")
    print("")

    # percorre tabelas candidatas que realmente existirem
    with engine.connect() as conn:
        for logical_name in TABLE_CANDIDATES:
            # tenta achar a mesa “correspondência” por nome exato primeiro
            table = available.get(logical_name)
            if table is None:
                # tenta variações comuns (plural/singular, underscores)
                # ex.: users, user; instrutor, instructor etc. (personalize se quiser)
                continue

            filt = build_filters(table, email_n, idfunc_n)
            if filt is None:
                continue

            try:
                cols = table.c.keys()
                stmt = select(table).where(filt).limit(50)
                rows = conn.execute(stmt).fetchall()
                # transforma Row em objeto simples com attrs para impressão uniforme
                RowObj = type("RowObj", (), {})
                norm_rows = []
                for row in rows:
                    o = RowObj()
                    for c in cols:
                        setattr(o, c, row[c])
                    norm_rows.append(o)
                print_rows(logical_name, norm_rows, cols)
            except SQLAlchemyError as e:
                print(f"[{logical_name}] erro ao consultar: {e}")

    print("=== FIM ===")

if __name__ == "__main__":
    main()