import sys
import os
from sqlalchemy import orm

sys.path.append(os.getcwd())

# Tenta carregar o App e forçar a configuração do Banco
print(">>> INICIANDO DIAGNÓSTICO DE MAPPERS <<<")
try:
    from backend.app import create_app
    from backend.models.database import db
    
    app = create_app()
    with app.app_context():
        print("1. App criado. Tentando configurar relacionamentos...")
        # Este comando obriga o SQLAlchemy a verificar todos os modelos AGORA
        orm.configure_mappers()
        print("2. SUCESSO! Mappers configurados corretamente.")
        
except Exception as e:
    print("\n" + "="*40)
    print("ERRO ENCONTRADO:")
    print("="*40)
    # Imprime o erro completo
    import traceback
    traceback.print_exc()
    print("="*40)