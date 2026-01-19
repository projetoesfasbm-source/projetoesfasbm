import sys
import os
from sqlalchemy import text
from sqlalchemy.orm import joinedload

# Configuração de caminho para importar o app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from backend.app import create_app
from backend.models.database import db
from backend.models.horario import Horario
from backend.models.disciplina import Disciplina
from backend.models.turma import Turma
from backend.models.school import School

app = create_app()

def diagnosticar():
    with app.app_context():
        print("\n=== DIAGNÓSTICO DE VÍNCULO DE HORÁRIOS ===")
        
        # 1. Buscar a turma pelo nome "Turma 01"
        nome_alvo = "Turma 01"
        turmas = Turma.query.filter_by(nome=nome_alvo).all()
        
        if not turmas:
            print(f"ERRO: Nenhuma turma encontrada com o nome '{nome_alvo}'.")
            return

        print(f"Encontradas {len(turmas)} turmas com nome '{nome_alvo}':")
        for t in turmas:
            print(f" - Turma ID: {t.id} | Escola ID: {t.school_id} | Status: {t.status}")

        print("\n--- ANALISANDO HORÁRIOS COM TEXTO 'Turma 01' ---")
        # 2. Buscar horários que tenham o texto "Turma 01", independente de links
        horarios = db.session.query(Horario).options(
            joinedload(Horario.disciplina).joinedload(Disciplina.turma)
        ).filter(Horario.pelotao == nome_alvo).limit(5).all()

        if not horarios:
            print("Nenhum horário encontrado com o texto 'Turma 01' no campo 'pelotao'.")
        else:
            for h in horarios:
                disc = h.disciplina
                turma_disc = disc.turma if disc else None
                
                print(f"\nHorário ID: {h.id} | Dia: {h.dia_semana} | Periodo: {h.periodo}")
                print(f" > Texto Pelotão: '{h.pelotao}'")
                
                if disc:
                    print(f" > Disciplina ID: {disc.id} | Nome: {disc.materia}")
                    print(f" > Disciplina vinculada à Turma ID: {disc.turma_id}")
                    
                    if turma_disc:
                        print(f"   > Dados da Turma Real (Via Disciplina): Nome='{turma_disc.nome}' | Escola ID={turma_disc.school_id}")
                    else:
                        print("   > ALERTA: Disciplina não tem turma vinculada (Orphan) ou ID inválido!")
                else:
                    print(" > ERRO CRÍTICO: Horário sem disciplina vinculada!")

        print("\n============================================")

if __name__ == "__main__":
    diagnosticar()