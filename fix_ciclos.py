import sys
sys.path.insert(0, '.')
from backend.app import create_app
from backend.models.database import db
from backend.models.edicao import Edicao
from backend.models.school import School
from backend.models.ciclo import Ciclo

app = create_app()
with app.app_context():
    schools = School.query.all()
    for s in schools:
        ed = Edicao.query.filter_by(school_id=s.id).order_by(Edicao.id).first()
        if ed:
            db.session.query(Ciclo).filter_by(school_id=s.id, edicao_id=None).update({'edicao_id': ed.id})
            db.session.commit()
            print('Updated Ciclos for school', s.id)
