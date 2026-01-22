import sys
import os

# Adiciona o diretório atual ao path
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
# Importa o novo modelo para que o SQLAlchemy o reconheça
from backend.models.admin_log import AdminLog 

app = create_app()

def setup_db():
    with app.app_context():
        print("\n" + "=" * 60)
        print("🛠️  CONFIGURAÇÃO DE TABELA DE LOGS")
        print("=" * 60)
        
        # Cria apenas as tabelas que ainda não existem
        # Isso é seguro e NÃO apaga dados existentes
        try:
            db.create_all()
            print("✅ Tabela 'admin_logs' verificada/criada com sucesso.")
            print("   Agora você pode acessar 'Ferramentas > Logs de Ações'.")
        except Exception as e:
            print(f"❌ Erro ao criar tabela: {e}")

if __name__ == "__main__":
    setup_db()