from backend.app import create_app
from backend.models.database import db
from backend.models.diario_classe import DiarioClasse
from backend.models.disciplina_turma import DisciplinaTurma

app = create_app()
with app.app_context():
    print("Iniciando reparo de vínculos de diários...")
    diarios_sem_instrutor = DiarioClasse.query.filter(
        (DiarioClasse.instrutor_id_1 == None) & (DiarioClasse.instrutor_id_2 == None)
    ).all()
    
    reparados = 0
    for diario in diarios_sem_instrutor:
        # Busca o vínculo correto pela disciplina
        vinculo = DisciplinaTurma.query.filter_by(disciplina_id=diario.disciplina_id).first()
        if vinculo:
            diario.instrutor_id_1 = vinculo.instrutor_id_1
            diario.instrutor_id_2 = vinculo.instrutor_id_2
            reparados += 1
            print(f"Reparado Diário ID {diario.id}: {diario.materia_nome}")
            
    db.session.commit()
    print(f"Fim. Total de aulas reparadas: {reparados}")