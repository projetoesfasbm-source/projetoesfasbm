import os
import sys

# Adiciona o diretório atual ao path para encontrar o backend
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
from backend.models.horario import Horario
from backend.models.turma import Turma
from backend.models.semana import Semana
from sqlalchemy import select

app = create_app()
with app.app_context():
    print("=== TESTE DE CERTEZA ABSOLUTA ===\n")
    
    # 1. Pegamos uma amostra real do que está na tabela de horários
    # Tentamos o ID 12425 que apareceu no seu diagnóstico
    exemplo_horario = db.session.get(Horario, 12425)
    
    if not exemplo_horario:
        # Fallback: pega o primeiro registro que encontrar
        exemplo_horario = db.session.execute(select(Horario).limit(1)).scalar()

    if exemplo_horario:
        nome_no_horario = exemplo_horario.pelotao
        semana_id_no_horario = exemplo_horario.semana_id
        print(f"DADO NA TABELA 'HORARIOS':")
        print(f"  - Pelotão gravado: '{nome_no_horario}'")
        print(f"  - Semana ID gravada: {semana_id_no_horario}")
        
        # 2. Verifica se a Turma existe com esse NOME EXATO
        turma_real = db.session.execute(select(Turma).where(Turma.nome == nome_no_horario)).scalar()
        
        # 3. Verifica se a Semana existe
        semana_real = db.session.get(Semana, semana_id_no_horario)
        
        print("\n--- VERIFICAÇÃO DE VÍNCULOS ---")
        
        if turma_real:
            print(f"[OK] Turma encontrada: ID {turma_real.id} corresponde ao nome '{nome_no_horario}'")
        else:
            print(f"[ERRO CRÍTICO] Nenhuma turma no cadastro tem o nome exato '{nome_no_horario}'")
            print(f"      Dica: O sistema não encontrará as aulas se o nome não for idêntico.")

        if semana_real:
            print(f"[OK] Semana ID {semana_id_no_horario} existe no banco.")
        else:
            print(f"[ERRO CRÍTICO] A Semana ID {semana_id_no_horario} NÃO existe mais no banco.")
            print(f"      Dica: Se a semana foi deletada, as aulas vinculadas a ela não aparecem.")

        # 4. Listar nomes reais das turmas para comparação
        print("\nNOMES DE TURMAS CADASTRADAS NO SISTEMA AGORA:")
        todas_turmas = db.session.execute(select(Turma)).scalars().all()
        for t in todas_turmas:
            print(f"  - '{t.nome}'")

    else:
        print("ERRO: A tabela 'horarios' parece estar vazia agora.")