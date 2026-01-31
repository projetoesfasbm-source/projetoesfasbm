from backend.app import create_app
from backend.models.database import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    print("Iniciando migração de colunas para DiarioClasse...")
    try:
        # Adiciona instrutor_id_1
        db.session.execute(text("ALTER TABLE diarios_classe ADD COLUMN instrutor_id_1 INTEGER REFERENCES instrutores(id)"))
        # Adiciona instrutor_id_2
        db.session.execute(text("ALTER TABLE diarios_classe ADD COLUMN instrutor_id_2 INTEGER REFERENCES instrutores(id)"))
        db.session.commit()
        print("Colunas criadas com sucesso!")
    except Exception as e:
        db.session.rollback()
        print(f"Aviso: Colunas podem já existir ou erro: {e}")

    print("Sincronizando instrutores dos vínculos para os diários existentes...")
    # Este bloco preenche os IDs vazios baseando-se no que já está no sistema
    from backend.models.diario_classe import DiarioClasse
    from backend.models.disciplina_turma import DisciplinaTurma

    diarios = DiarioClasse.query.all()
    for d in diarios:
        vinculo = DisciplinaTurma.query.filter_by(disciplina_id=d.disciplina_id).first()
        if vinculo:
            d.instrutor_id_1 = vinculo.instrutor_id_1
            d.instrutor_id_2 = vinculo.instrutor_id_2
    
    db.session.commit()
    print("Migração concluída e dados sincronizados!")