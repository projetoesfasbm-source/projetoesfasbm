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
        print("VARREDURA FINAL DE REPARO (TODAS AS TABELAS)")
        print("="*60)

        # LISTA COMPLETA DE COLUNAS FALTANTES BASEADA NOS LOGS
        correcoes = [
            # Tabela DIARIOS_CLASSE
            ('diarios_classe', 'status', "VARCHAR(50) DEFAULT 'pendente'"),
            ('diarios_classe', 'updated_at', 'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'),
            ('diarios_classe', 'created_at', 'DATETIME DEFAULT CURRENT_TIMESTAMP'),
            ('diarios_classe', 'assinatura_path', 'VARCHAR(255) DEFAULT NULL'),
            ('diarios_classe', 'data_assinatura', 'DATETIME DEFAULT NULL'),
            ('diarios_classe', 'instrutor_assinante_id', 'INT DEFAULT NULL'),

            # Tabela SEMANAS (Configurações de Prioridade e Fim de Semana)
            ('semanas', 'priority_blocks', 'TEXT DEFAULT NULL'),
            ('semanas', 'priority_active', 'BOOLEAN DEFAULT 0'),
            ('semanas', 'priority_disciplines', 'TEXT DEFAULT NULL'),
            ('semanas', 'mostrar_periodo_13', 'BOOLEAN DEFAULT 0'),
            ('semanas', 'mostrar_periodo_14', 'BOOLEAN DEFAULT 0'),
            ('semanas', 'mostrar_periodo_15', 'BOOLEAN DEFAULT 0'),
            ('semanas', 'mostrar_sabado', 'BOOLEAN DEFAULT 0'),
            ('semanas', 'periodos_sabado', 'TEXT DEFAULT NULL'),
            ('semanas', 'mostrar_domingo', 'BOOLEAN DEFAULT 0'),
            ('semanas', 'periodos_domingo', 'TEXT DEFAULT NULL'),

            # Tabela CICLOS
            ('ciclos', 'data_inicio', 'DATE DEFAULT NULL'),
            ('ciclos', 'data_fim', 'DATE DEFAULT NULL'),

            # Tabela INSTRUTORES
            ('instrutores', 'assinatura_padrao_path', 'VARCHAR(255) DEFAULT NULL'),
            ('instrutores', 'is_rr', 'BOOLEAN DEFAULT 0'),
            
            # Tabela TURMAS
            ('turmas', 'data_formatura', 'DATE DEFAULT NULL'),
            ('turmas', 'status', "VARCHAR(20) DEFAULT 'ativa'")
        ]

        print("Iniciando reparo total...\n")

        for tabela, coluna, tipo in correcoes:
            try:
                print(f"> Verificando {tabela}.{coluna}...", end=" ")
                sql = text(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo};")
                session.execute(sql)
                session.commit()
                print("✅ CORRIGIDO")
            except Exception as e:
                session.rollback()
                msg = str(e).lower()
                if "duplicate column" in msg or "exists" in msg or "1060" in msg:
                    print("🆗 OK (Já existe)")
                elif "doesn't exist" in msg and "table" in msg:
                    print(f"⚠️  TABELA '{tabela}' NÃO EXISTE")
                else:
                    print(f"\n❌ ERRO: {e}")

        print("\n" + "="*60)
        print("REPARO FINALIZADO.")
        print("Tente acessar o Painel e os Diários novamente.")

except Exception as e:
    print(f"Erro Crítico: {e}")