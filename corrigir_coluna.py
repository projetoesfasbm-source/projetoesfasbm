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
    # Removemos a importação direta do db para evitar o erro de contexto
    # from models.database import db 
    
    app = create_app()

    # Função auxiliar para garantir a conexão correta
    def get_session(app_inst):
        if 'sqlalchemy' in app_inst.extensions:
            sa = app_inst.extensions['sqlalchemy']
            # Tenta pegar a sessão de formas diferentes dependendo da versão do Flask-SQLAlchemy
            if hasattr(sa, 'session'): return sa.session
            elif hasattr(sa, 'db'): return sa.db.session
        
        # Fallback (Plano B)
        from models.database import db
        return db.session

    with app.app_context():
        # Pegamos a sessão ativa do app
        session = get_session(app)

        print("\n" + "="*60)
        print("CORRETOR DE ESTRUTURA DO BANCO DE DADOS (CONTEXTO SEGURO)")
        print("="*60)
        print("Tentando adicionar a coluna 'data_registro' na tabela 'processos_disciplina'...\n")

        try:
            # Comando SQL para criar a coluna que falta
            sql = text("ALTER TABLE processos_disciplina ADD COLUMN data_registro DATETIME DEFAULT NULL;")
            
            session.execute(sql)
            session.commit()
            
            print("✅ SUCESSO! A coluna 'data_registro' foi criada.")
            print("O erro 1054 deve desaparecer agora.")
            
        except Exception as e:
            session.rollback()
            # Tratamento de erro se a coluna já existir
            err_msg = str(e).lower()
            if "duplicate column" in err_msg or "exists" in err_msg:
                print("⚠️  Aviso: A coluna parece já existir (O banco já estava corrigido).")
            else:
                print(f"❌ Erro ao tentar alterar a tabela: {e}")

except Exception as e:
    print(f"Erro Crítico ao carregar app: {e}")