import os
import sys
from datetime import datetime, timedelta

# Garante que o Python encontre a pasta backend
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
from backend.models.horario import Horario
from backend.models.diario_classe import DiarioClasse
from backend.models.semana import Semana
from backend.models.disciplina import Disciplina

def get_data_real(data_inicio_semana, dia_semana_texto):
    """Converte o texto do dia da semana em uma data real baseada no início da semana."""
    dias = {
        'segunda': 0, 'terça': 1, 'quarta': 2, 'quinta': 3, 
        'sexta': 4, 'sábado': 5, 'domingo': 6,
        'segunda-feira': 0, 'terça-feira': 1, 'quarta-feira': 2, 
        'quinta-feira': 3, 'sexta-feira': 4
    }
    # Normaliza o texto para busca
    dia_clean = dia_semana_texto.lower().strip()
    offset = dias.get(dia_clean, 0)
    return data_inicio_semana + timedelta(days=offset)

def validar_integridade():
    app = create_app()
    with app.app_context():
        print(f"\n{'='*100}")
        print(f" RELATÓRIO DE INTEGRIDADE: QUADRO HORÁRIO vs DIÁRIO DE CLASSE")
        print(f" Data do Diagnóstico: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"{'='*100}\n")

        # Busca horários agendados ordenados pela semana
        horarios = Horario.query.join(Semana).order_by(Semana.data_inicio.desc(), Horario.periodo).all()

        total_horarios = len(horarios)
        com_diario = 0
        sem_diario = 0

        print(f"{'DATA AULA':<12} | {'TURMA':<12} | {'DISCIPLINA':<25} | {'STATUS NO FLUXO'}")
        print(f"{'-'*100}")

        for h in horarios:
            # Calcula a data real da aula para cruzar com o diário
            data_aula_real = get_data_real(h.semana.data_inicio, h.dia_semana)
            
            # Busca o Diário correspondente
            # A lógica de cruzamento oficial: Mesma Data + Mesma Disciplina + Mesmo Período + Mesma Turma
            diario = DiarioClasse.query.filter(
                DiarioClasse.data_aula == data_aula_real,
                DiarioClasse.disciplina_id == h.disciplina_id,
                DiarioClasse.periodo == h.periodo,
                DiarioClasse.turma_id == h.disciplina.turma_id # Usa o ID da turma vinculado à disciplina
            ).first()

            data_str = data_aula_real.strftime('%d/%m/%Y')
            turma_nome = h.pelotao[:11]
            disc_nome = h.disciplina.materia[:24]

            if diario:
                com_diario += 1
                if diario.status == 'assinado':
                    status_desc = "✅ CONCLUÍDO (Assinado)"
                else:
                    status_desc = "📩 COM INSTRUTOR (Aguardando Assinatura)"
            else:
                sem_diario += 1
                status_desc = "❌ COM ALUNO (Não lançado pelo Chefe de Turma)"

            print(f"{data_str:<12} | {turma_nome:<12} | {disc_nome:<25} | {status_desc}")

        print(f"\n{'='*100}")
        print(f" RESUMO FINAL:")
        print(f" Total agendado no Quadro Horário: {total_horarios}")
        print(f" Total enviado ao Instrutor:      {com_diario}")
        print(f" Total parado com o Aluno:         {sem_diario}")
        print(f"{'='*100}\n")

if __name__ == "__main__":
    validar_integridade()