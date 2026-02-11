import os
import sys
sys.path.append(os.getcwd())
from backend.app import create_app
from backend.models.database import db
from backend.models.horario import Horario
from backend.models.semana import Semana
from sqlalchemy import select, func

app = create_app()
with app.app_context():
    print("=== RELATÓRIO DE LACUNAS (PORTO ALEGRE - CICLO 4) ===\n")
    
    # Pegamos todas as semanas do Ciclo 4 (Porto Alegre)
    semanas = db.session.scalars(select(Semana).where(Semana.ciclo_id == 4).order_by(Semana.id)).all()
    
    # Focamos na Turma 09 (A pivô do problema)
    turma_alvo = '09° Pelotão - CBFPM 2026'
    
    for s in semanas:
        qtd = db.session.scalar(
            select(func.count(Horario.id))
            .where(Horario.pelotao == turma_alvo, Horario.semana_id == s.id)
        )
        status = "[OK]" if qtd > 0 else "[!!!] VAZIA (FOI APAGADA)"
        print(f"Semana: {s.nome:<15} (ID {s.id:>3}) | Aulas encontradas: {qtd:>2} | {status}")

    print("\n---")
    print("Se o resultado acima mostrar várias semanas como 'VAZIA', o plano é:")
    print(f"Usar a primeira semana que estiver [OK] para repopular as que foram apagadas.")