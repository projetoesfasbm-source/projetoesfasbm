import sys
import os
from unittest.mock import MagicMock

# ----- MOCKS PARA EVITAR QUEBRA DE IMPORTS -----
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.auth"] = MagicMock()
sys.modules["docx"] = MagicMock()
sys.modules["docx.shared"] = MagicMock()
sys.modules["docx.enum.text"] = MagicMock()
# -----------------------------------------------

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app import create_app
from backend.models.database import db
from sqlalchemy import text

app = create_app()

SQL = """
ALTER TABLE semanas
ADD COLUMN priority_blocks TEXT NULL;
"""

with app.app_context():
    try:
        db.session.execute(text(SQL))
        db.session.commit()
        print("✅ COLUNA priority_blocks CRIADA COM SUCESSO!")
    except Exception as e:
        db.session.rollback()
        print("❌ ERRO AO CRIAR COLUNA:", e)
