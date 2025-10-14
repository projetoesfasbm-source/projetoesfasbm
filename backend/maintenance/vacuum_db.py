# backend/maintenance/vacuum_db.py
import os
import sys
from importlib import import_module
from sqlalchemy import create_engine, text

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
    print("Iniciando o procedimento de manutenção da base de dados...")
    ensure_project_on_path()
    app = build_app()
    with app.app_context():
        uri = app.config.get("SQLALCHEMY_DATABASE_URI")
        if not uri:
            raise RuntimeError("SQLALCHEMY_DATABASE_URI não encontrada.")
        print(f"A conectar a: {uri}")

    engine = create_engine(uri)
    try:
        with engine.connect() as connection:
            # O VACUUM precisa de ser executado fora de uma transação explícita em algumas versões/drivers
            connection.execution_options(isolation_level="AUTOCOMMIT")
            print("Executando o comando VACUUM... Isto pode demorar alguns momentos.")
            connection.execute(text("VACUUM;"))
            print("O comando VACUUM foi concluído com sucesso.")

        print("\nA base de dados foi reconstruída e os índices foram otimizados.")
        print("Quaisquer registos 'fantasma' deverão ter sido removidos.")

    except Exception as e:
        print(f"\nOcorreu um erro durante a manutenção: {e}")
        print("O procedimento foi interrompido.")

if __name__ == "__main__":
    main()