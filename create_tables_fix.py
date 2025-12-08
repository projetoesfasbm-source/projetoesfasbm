from backend.app import create_app
from backend.models.database import db

# Importar os modelos para garantir que o SQLAlchemy os reconheça
from backend.models.diario_classe import DiarioClasse
from backend.models.frequencia import FrequenciaAluno

app = create_app()

with app.app_context():
    print("Criando tabelas faltantes...")
    try:
        db.create_all()
        print("Sucesso! As tabelas 'diarios_classe' e 'frequencias_alunos' foram criadas.")
    except Exception as e:
        print(f"Erro ao criar tabelas: {e}")