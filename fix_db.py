import sys
sys.path.insert(0, '.')
from backend.app import create_app
from backend.models.database import db
from backend.models.edicao import Edicao
from backend.models.school import School
from backend.models.turma import Turma
from backend.models.aluno import Aluno
from backend.models.processo_disciplina import ProcessoDisciplina

app = create_app()
with app.app_context():
    schools = School.query.all()
    for s in schools:
        ed = Edicao.query.filter_by(school_id=s.id).order_by(Edicao.id).first()
        if ed:
            db.session.query(Turma).filter_by(school_id=s.id, edicao_id=None).update({'edicao_id': ed.id})
            db.session.query(Aluno).filter(Aluno.edicao_id == None, Aluno.turma_id.in_(db.session.query(Turma.id).filter_by(school_id=s.id))).update({'edicao_id': ed.id}, synchronize_session=False)
            db.session.commit()
            print('Updated school', s.id)
