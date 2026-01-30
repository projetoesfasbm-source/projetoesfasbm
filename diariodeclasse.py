from backend.app import create_app
from backend.models.database import db
from backend.models.diario_classe import DiarioClasse
from backend.models.horario import Horario
from backend.models.turma import Turma
from sqlalchemy import select

app = create_app()
with app.app_context():
    # Localiza a turma pelo ID ou nome real para evitar erro de string
    t = db.session.execute(select(Turma).where(Turma.nome.like('%9%'))).scalars().first()
    if t:
        print(f"Verificando Turma ID: {t.id} - Nome: {t.nome}")
        
        print("\n--- REGISTROS NO DIÁRIO (O que o aluno enviou) ---")
        diarios = db.session.execute(select(DiarioClasse).filter_by(turma_id=t.id)).scalars().all()
        for d in diarios:
            print(f"Data: {d.data_aula} | Período: {d.periodo} | Disciplina ID: {d.disciplina_id} | Status: {d.status}")

        print("\n--- REGISTROS NO QUADRO DE HORÁRIOS (NPCCAL) ---")
        horarios = db.session.execute(select(Horario).filter_by(pelotao=t.nome)).scalars().all()
        for h in horarios:
            print(f"Dia: {h.dia_semana} | Período: {h.periodo} | Disciplina ID: {h.disciplina_id} | Inst1: {h.instrutor_id} | Inst2: {h.instrutor_id_2}")