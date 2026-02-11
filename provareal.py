import os
import sys
sys.path.append(os.getcwd())
from backend.app import create_app
from backend.models.database import db
from backend.models.horario import Horario
from backend.models.semana import Semana
from backend.models.ciclo import Ciclo
from sqlalchemy import select

app = create_app()
with app.app_context():
    print("=== LOCALIZADOR DE AULAS INVISÍVEIS ===\n")
    
    # Vamos pegar o Pelotão 9 como exemplo real
    pelotao_alvo = '09° Pelotão - CBFPM 2026'
    
    aulas = db.session.execute(
        select(Horario.semana_id, Semana.ciclo_id, Ciclo.nome, Ciclo.school_id)
        .join(Semana, Horario.semana_id == Semana.id)
        .join(Ciclo, Semana.ciclo_id == Ciclo.id)
        .where(Horario.pelotao == pelotao_alvo)
        .distinct()
    ).all()

    if not aulas:
        print(f"Nenhuma aula encontrada para {pelotao_alvo}")
    else:
        print(f"As aulas do {pelotao_alvo} estão distribuídas assim:")
        for sem_id, cic_id, cic_nome, sch_id in aulas:
            print(f" -> Na Semana ID {sem_id}, que pertence ao CICLO ID {cic_id} ('{cic_nome}') na ESCOLA ID {sch_id}")

    print("\n---")
    print("O MOTIVO DO VAZIO:")
    print("Verifique se o Ciclo e a Escola que aparecem acima são os mesmos que você selecionou na tela.")
    print("Se forem diferentes, o sistema nunca mostrará as aulas, mesmo elas existindo.")