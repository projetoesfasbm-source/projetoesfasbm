import sys
import os

# Adiciona o diretório atual ao path para importar o backend
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
from backend.models.horario import Horario
from backend.models.semana import Semana
from backend.models.turma import Turma
from backend.models.disciplina import Disciplina

app = create_app()

def diagnostico_aulas():
    with app.app_context():
        print("=== INICIANDO DIAGNÓSTICO DE AULAS (HORÁRIOS) ===\n")
        
        horarios = Horario.query.all()
        
        if not horarios:
            print("[-] NENHUMA aula (registro na tabela 'horarios') encontrada no banco de dados.")
            return

        print(f"[+] Total de registros encontrados na tabela 'horarios': {len(horarios)}\n")
        print(f"{'ID':<6} | {'Pelotão (Horário)':<20} | {'Semana':<20} | {'Matéria':<25} | {'Status':<10}")
        print("-" * 95)

        for h in horarios:
            # Busca a semana (Sintaxe 2.0)
            semana = db.session.get(Semana, h.semana_id)
            nome_semana = semana.nome if semana else f"ERRO: ID {h.semana_id} N/EXISTE"
            
            # Busca a disciplina (Sintaxe 2.0)
            disc = db.session.get(Disciplina, h.disciplina_id)
            nome_materia = disc.materia if disc else f"ERRO: ID {h.disciplina_id} N/EXISTE"
            
            # Verifica se o pelotao (string) existe na tabela turmas pelo nome
            turma_venculada = Turma.query.filter_by(nome=h.pelotao).first()
            aviso_turma = "" if turma_venculada else " [!] TURMA N/LOCALIZADA"

            print(f"{h.id:<6} | {h.pelotao + aviso_turma:<20} | {nome_semana:<20} | {nome_materia:<25} | {h.status:<10}")

        print("\n=== FIM DO DIAGNÓSTICO ===")

if __name__ == "__main__":
    diagnostico_aulas()