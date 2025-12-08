# setup_tabelas.py
import sys
import os

# Adiciona o diretório atual ao path para encontrar o backend
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db

# IMPORTANTE: Importar os modelos explicitamente para o SQLAlchemy registrá-los
from backend.models.diario_classe import DiarioClasse
from backend.models.frequencia import FrequenciaAluno
from backend.models.turma_cargo import TurmaCargo

app = create_app()

with app.app_context():
    print("--- INICIANDO CRIAÇÃO DE TABELAS ---")
    try:
        # Tenta criar todas as tabelas definidas nos models
        db.create_all()
        db.session.commit()
        print("✅ SUCESSO: Tabelas 'diarios_classe' e 'frequencias_alunos' verificadas/criadas.")
        
        # Verificação extra
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if 'diarios_classe' in tables and 'frequencias_alunos' in tables:
            print("🔍 CONFIRMAÇÃO: As tabelas existem fisicamente no banco.")
        else:
            print("❌ ERRO: O comando rodou, mas as tabelas não aparecem na listagem.")
            
    except Exception as e:
        print(f"❌ ERRO FATAL: {e}")