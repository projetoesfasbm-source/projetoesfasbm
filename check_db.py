from backend.app import create_app
from backend.models.database import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("="*60)
    print("BANCO EM USO PELO FLASK:")
    print(db.engine.url)
    print("="*60)

    try:
        r = db.session.execute(text("SELECT version_num FROM alembic_version"))
        print("VERSÃO ALEMBIC NO BANCO:", r.scalar())
    except Exception as e:
        print("NÃO EXISTE alembic_version AINDA")
