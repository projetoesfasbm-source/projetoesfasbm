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
        print("REPARADOR FINAL DE TABELAS (CICLOS, SEMANAS, DIARIOS)")
        print("="*60)

        correcoes = [
            # 1. Tabela CICLOS (Erro 'Unknown column data_inicio')
            ('ciclos', 'data_inicio', 'DATE DEFAULT NULL'),
            ('ciclos', 'data_fim', 'DATE DEFAULT NULL'),

            # 2. Tabela DIARIOS_CLASSE (Erro 'Unknown column status')
            ('diarios_classe', 'status', "VARCHAR(50) DEFAULT 'pendente'"),
            ('diarios_classe', 'assinatura_path', 'VARCHAR(255) DEFAULT NULL'),
            ('diarios_classe', 'data_assinatura', 'DATETIME DEFAULT NULL'),
            ('diarios_classe', 'instrutor_assinante_id', 'INT DEFAULT NULL'),

            # 3. Tabela SEMANAS (Erro 'Unknown column priority_blocks')
            # Adicionando pacote de colunas novas de configuração
            ('semanas', 'priority_active', 'BOOLEAN DEFAULT 0'),
            ('semanas', 'priority_disciplines', 'TEXT DEFAULT NULL'),
            ('semanas', 'priority_blocks', 'TEXT DEFAULT NULL'),
            ('semanas', 'mostrar_periodo_13', 'BOOLEAN DEFAULT 0'),
            ('semanas', 'mostrar_periodo_14', 'BOOLEAN DEFAULT 0'),
            ('semanas', 'mostrar_periodo_15', 'BOOLEAN DEFAULT 0'),
            ('semanas', 'mostrar_sabado', 'BOOLEAN DEFAULT 0'),
            ('semanas', 'periodos_sabado', 'TEXT DEFAULT NULL'),
            ('semanas', 'mostrar_domingo', 'BOOLEAN DEFAULT 0'),
            ('semanas', 'periodos_domingo', 'TEXT DEFAULT NULL')
        ]

        print("Aplicando correções em massa...\n")

        for tabela, coluna, tipo in correcoes:
            try:
                print(f"> {tabela}.{coluna}...", end=" ")
                sql = text(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo};")
                session.execute(sql)
                session.commit()
                print("✅ CRIADO")
            except Exception as e:
                session.rollback()
                msg = str(e).lower()
                if "duplicate column" in msg or "exists" in msg or "1060" in msg:
                    print("🆗 JÁ EXISTE")
                elif "doesn't exist" in msg and "table" in msg:
                    print(f"⚠️  TABELA '{tabela}' NÃO EXISTE")
                else:
                    print(f"\n❌ ERRO: {e}")

        print("\n" + "="*60)
        print("DIAGNÓSTICO CONCLUÍDO.")
        print("Acesse o sistema novamente e verifique os menus 'Horário' e 'Diário'.")

except Exception as e:
    print(f"Erro Crítico: {e}")