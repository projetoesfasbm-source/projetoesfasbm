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
        print("REPARADOR GERAL DE BANCO DE DADOS (TURMAS + INSTRUTORES)")
        print("="*60)

        # LISTA DE CORREÇÕES NECESSÁRIAS
        # Formato: (nome_tabela, nome_coluna, tipo_sql)
        correcoes = [
            # Tabela TURMAS
            ('turmas', 'data_formatura', 'DATE DEFAULT NULL'),
            ('turmas', 'status', "VARCHAR(20) DEFAULT 'ativa'"),  # Previne erro futuro
            
            # Tabela INSTRUTORES
            ('instrutores', 'assinatura_padrao_path', 'VARCHAR(255) DEFAULT NULL'),
            ('instrutores', 'is_rr', 'BOOLEAN DEFAULT 0'),  # Campo comum em versões novas
            
            # Tabela PROCESSOS (Reforço caso tenha faltado algo)
            ('processos_disciplina', 'data_registro', 'DATETIME DEFAULT NULL'),
            ('processos_disciplina', 'observacao_decisao', 'TEXT DEFAULT NULL'),
            ('processos_disciplina', 'detalhes_sancao', 'TEXT DEFAULT NULL')
        ]

        print("Iniciando verificação e reparo...\n")

        for tabela, coluna, tipo in correcoes:
            try:
                print(f"> Verificando '{tabela}.{coluna}'...", end=" ")
                
                # Monta o SQL de alteração
                sql = text(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo};")
                
                session.execute(sql)
                session.commit()
                print("✅ CRIADA")
                
            except Exception as e:
                session.rollback()
                msg = str(e).lower()
                # Se o erro for "Duplicate column", é boa notícia (já existe)
                if "duplicate column" in msg or "exists" in msg or "1060" in msg:
                    print("🆗 JÁ EXISTE")
                elif "doesn't exist" in msg and "table" in msg:
                    print(f"⚠️  TABELA '{tabela}' NÃO ENCONTRADA")
                else:
                    print(f"\n❌ ERRO: {e}")

        print("\n" + "="*60)
        print("DIAGNÓSTICO FINALIZADO.")
        print("Tente atualizar a página do sistema agora.")

except Exception as e:
    print(f"Erro Crítico: {e}")