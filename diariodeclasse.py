from backend.app import create_app
from backend.models.database import db
from backend.models.diario_classe import DiarioClasse
from backend.models.horario import Horario
from backend.models.turma import Turma
from sqlalchemy import select

app = create_app()
with app.app_context():
    # Buscando a Turma 9 pelo ID 45 que você confirmou
    t_id = 45
    print(f"--- ANALISANDO VÍNCULOS DA TURMA ID: {t_id} ---")

    # 1. Ver o que está gravado nos Diários (enviados pelo aluno)
    print("\n[TABELA DIARIO_CLASSE] - O que o aluno enviou:")
    diarios = db.session.execute(
        select(DiarioClasse).filter_by(turma_id=t_id).order_by(DiarioClasse.data_aula.desc())
    ).scalars().all()
    for d in diarios:
        print(f"Data: {d.data_aula} | ID Disciplina: {d.disciplina_id} | Período: {d.periodo} | Status: {d.status}")

    # 2. Ver o que está no Quadro de Horários para essa mesma turma
    print("\n[TABELA HORARIOS] - O que está no Quadro Horário:")
    turma = db.session.get(Turma, t_id)
    horarios = db.session.execute(
        select(Horario).filter_by(pelotao=turma.nome)
    ).scalars().all()
    for h in horarios:
        print(f"Dia: {h.dia_semana} | ID Disciplina: {h.disciplina_id} | Período: {h.periodo} | Inst1 (ID): {h.instrutor_id} | Inst2 (ID): {h.instrutor_id_2}")