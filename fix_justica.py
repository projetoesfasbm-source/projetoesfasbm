import os
from dotenv import load_dotenv

load_dotenv()

from backend.app import create_app
from backend.models.database import db
from backend.models.processo_disciplina import ProcessoDisciplina, StatusProcesso

def revert_stuck_processes():
    app = create_app()
    with app.app_context():
        # Find all processes that are ALUNO_NOTIFICADO but have no prazo_defesa
        stuck_processes = ProcessoDisciplina.query.filter_by(
            status=StatusProcesso.ALUNO_NOTIFICADO.value,
            prazo_defesa=None
        ).all()
        
        count = 0
        for p in stuck_processes:
            p.status = StatusProcesso.AGUARDANDO_CIENCIA.value
            p.ciente_aluno = False
            p.data_ciencia = None
            count += 1
            print(f"Reverting process {p.id} back to AGUARDANDO_CIENCIA")
            
        db.session.commit()
        print(f"Total reverted: {count}")

if __name__ == '__main__':
    revert_stuck_processes()
