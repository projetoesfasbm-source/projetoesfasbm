import os
import sys
sys.path.append(os.getcwd())
from backend.app import create_app
from backend.models.database import db
from backend.models.horario import Horario

app = create_app()
with app.app_context():
    print("Gerando arquivo de restauração completa...")
    horarios = Horario.query.all()
    
    with open('RESTAURACAO_MASTER.txt', 'w', encoding='utf-8') as f:
        # Cabeçalho com as colunas vitais
        f.write("PELOTAO|SEMANA_ID|DIA_SEMANA|PERIODO|DURACAO|DISCIPLINA_ID|INSTRUTOR_ID|INSTRUTOR_ID_2|STATUS|OBS\n")
        
        for h in horarios:
            # Extraímos os dados técnicos puros para não haver erro de nome
            linha = f"{h.pelotao}|{h.semana_id}|{h.dia_semana}|{h.periodo}|{h.duracao}|{h.disciplina_id}|{h.instrutor_id}|{h.instrutor_id_2}|{h.status}|{h.observacao}\n"
            f.write(linha)
    
    print(f"Sucesso! {len(horarios)} registros exportados para RESTAURACAO_MASTER.txt")