import os
import sys
sys.path.append(os.getcwd())
from backend.app import create_app
from backend.models.database import db
from backend.models.horario import Horario
from backend.models.semana import Semana
from backend.models.ciclo import Ciclo

app = create_app()
with app.app_context():
    print("=== TRANSPLANTE COM TRAVA DE SEGURANÇA (ANTI-COLISÃO) ===\n")
    
    aulas = Horario.query.all()
    corrigidos = 0
    conflitos = 0

    for a in aulas:
        sem = db.session.get(Semana, a.semana_id)
        if not sem: continue
        ciclo = db.session.get(Ciclo, sem.ciclo_id)
        escola_id = ciclo.school_id
        t = a.pelotao.upper()
        
        novo_id_semana = None

        # Aplica as suas regras de ouro para definir o destino correto
        if any(f"TURMA 0{i}" in t for i in range(1, 9)) and escola_id != 1:
            novo_id_semana = 11 
        elif any(f"TURMA {i}" in t for i in range(11, 21)) and escola_id != 13:
            novo_id_semana = 36
        elif ("PELOTÃO" in t or "PELOTAO" in t) and escola_id != 14:
            novo_id_semana = 23

        if novo_id_semana:
            # VERIFICAÇÃO ANTI-COLISÃO:
            # Existe alguém já ocupando este "quadradinho" no destino?
            colisao = Horario.query.filter_by(
                semana_id=novo_id_semana,
                dia_semana=a.dia_semana,
                periodo=a.periodo,
                pelotao=a.pelotao
            ).first()

            if colisao:
                # Se já tem aula nova lá, não mexemos para não estragar o trabalho atual
                conflitos += 1
                continue 
            
            a.semana_id = novo_id_semana
            corrigidos += 1

    print(f"Relatório:")
    print(f"- Aulas prontas para voltar ao lugar certo: {corrigidos}")
    print(f"- Aulas mantidas onde estão (conflito com marcações novas): {conflitos}")

    if corrigidos > 0:
        confirmar = input("\nDeseja aplicar o transplante nas aulas sem conflito? (s/n): ")
        if confirmar.lower() == 's':
            db.session.commit()
            print("[SUCESSO] O sistema foi reorganizado respeitando as novas marcações.")
        else:
            db.session.rollback()
            print("[ABORTADO]")