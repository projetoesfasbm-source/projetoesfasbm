import sys
import os
from sqlalchemy import text

# --- CONFIGURAÇÃO DE CAMINHO ---
basedir = os.path.abspath(os.path.dirname(__file__))
backend_path = os.path.join(basedir, 'backend')
if os.path.exists(backend_path) and backend_path not in sys.path:
    sys.path.insert(0, backend_path)

try:
    from app import create_app
    app = create_app()

    def get_session(app_inst):
        if 'sqlalchemy' in app_inst.extensions:
            sa = app_inst.extensions['sqlalchemy']
            if hasattr(sa, 'session'): return sa.session
            elif hasattr(sa, 'db'): return sa.db.session
        from models.database import db
        return db.session

    with app.app_context():
        session = get_session(app)
        print("\n" + "="*60)
        print("REPARO DE EMERGÊNCIA - COLUNAS FALTANTES")
        print("="*60)

        # LISTA DE CORREÇÕES CRÍTICAS IDENTIFICADAS NOS LOGS
        correcoes = [
            # (Tabela, Coluna, Definição SQL)
            ('instrutores', 'assinatura_padrao_path', 'VARCHAR(255) DEFAULT NULL'),
            ('instrutores', 'is_rr', 'BOOLEAN DEFAULT 0'),
            ('turmas', 'data_formatura', 'DATE DEFAULT NULL'),
            ('turmas', 'status', "VARCHAR(20) DEFAULT 'ativa'")
        ]

        for tabela, coluna, tipo in correcoes:
            print(f"> Verificando '{tabela}.{coluna}'...", end=" ")
            try:
                # Tenta adicionar a coluna diretamente
                sql = text(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo};")
                session.execute(sql)
                session.commit()
                print("✅ SUCESSO: Coluna criada.")
            except Exception as e:
                session.rollback()
                erro_str = str(e).lower()
                # Se o erro for de duplicidade, significa que já existe (o que é bom)
                if "duplicate column" in erro_str or "exists" in erro_str or "1060" in erro_str:
                    print("🆗 JÁ EXISTE.")
                else:
                    print(f"\n❌ ERRO: {e}")

        print("\n" + "="*60)
        print("PRONTO. Tente atualizar a página do site agora.")

except Exception as e:
    print(f"Erro Crítico ao carregar app: {e}")