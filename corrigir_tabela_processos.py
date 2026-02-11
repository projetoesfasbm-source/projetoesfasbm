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
        print("REPARADOR DE TABELA: PROCESSOS_DISCIPLINA")
        print("="*60)

        # Lista de colunas que costumam faltar em backups antigos
        # Formato: (nome_coluna, tipo_sql)
        colunas_para_adicionar = [
            ('observacao_decisao', 'TEXT DEFAULT NULL'),
            ('detalhes_sancao', 'TEXT DEFAULT NULL'),
            ('fundamentacao', 'TEXT DEFAULT NULL'),
            ('is_crime', 'BOOLEAN DEFAULT 0'),
            ('tipo_sancao', 'VARCHAR(100) DEFAULT NULL'),
            ('dias_sancao', 'INT DEFAULT 0'),
            ('origem_punicao', 'VARCHAR(100) DEFAULT NULL'),
            ('ciente_aluno', 'BOOLEAN DEFAULT 0'),
            ('data_registro', 'DATETIME DEFAULT NULL') # Caso o anterior tenha falhado
        ]

        tabela = 'processos_disciplina'
        
        print(f"Verificando colunas na tabela '{tabela}'...\n")

        for col, tipo in colunas_para_adicionar:
            try:
                # Tenta adicionar a coluna
                print(f"> Adicionando '{col}'...", end=" ")
                sql = text(f"ALTER TABLE {tabela} ADD COLUMN {col} {tipo};")
                session.execute(sql)
                session.commit()
                print("✅ SUCESSO")
            except Exception as e:
                session.rollback()
                msg = str(e).lower()
                if "duplicate column" in msg or "exists" in msg:
                    print("⚠️  JÁ EXISTE (Ignorado)")
                else:
                    print(f"\n❌ ERRO: {e}")

        print("\n" + "="*60)
        print("CONCLUÍDO. Tente acessar o sistema novamente.")

except Exception as e:
    print(f"Erro Crítico: {e}")