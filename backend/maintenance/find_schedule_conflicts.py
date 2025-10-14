# backend/maintenance/find_schedule_conflicts.py

import os
import sys
from collections import defaultdict
from sqlalchemy import select, delete

# Adiciona o diretório raiz do projeto ao path para encontrar os módulos
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

# Importa os componentes da aplicação
from backend.app import create_app
from backend.models.database import db
from backend.models.horario import Horario
from backend.models.semana import Semana
from backend.models.disciplina import Disciplina

def find_conflicts():
    """
    Diagnostica e, opcionalmente, limpa conflitos de horário no banco de dados.
    """
    apply_changes = '--apply' in sys.argv
    
    app = create_app()
    with app.app_context():
        print("Iniciando a verificação de conflitos de horário...")

        # Agrupa todos os horários por turma, semana e dia para otimizar a verificação
        horarios_agrupados = defaultdict(list)
        todos_horarios = db.session.scalars(select(Horario).options(
            db.joinedload(Horario.disciplina),
            db.joinedload(Horario.semana)
        )).all()

        for h in todos_horarios:
            chave = (h.pelotao, h.semana_id, h.dia_semana)
            horarios_agrupados[chave].append(h)

        conflitos_encontrados = 0
        ids_para_deletar = set()

        # Itera sobre cada grupo para encontrar sobreposições
        for chave, horarios in horarios_agrupados.items():
            pelotao, semana_id, dia = chave
            
            # Ordena por período para uma verificação sequencial
            horarios.sort(key=lambda x: x.periodo)
            
            for i in range(len(horarios)):
                h1 = horarios[i]
                h1_periodos = set(range(h1.periodo, h1.periodo + h1.duracao))
                
                for j in range(i + 1, len(horarios)):
                    h2 = horarios[j]
                    
                    # Otimização: se o segundo horário começa depois que o primeiro termina, não há conflito
                    if h2.periodo >= h1.periodo + h1.duracao:
                        continue

                    h2_periodos = set(range(h2.periodo, h2.periodo + h2.duracao))
                    
                    # Se houver qualquer interseção de períodos, é um conflito
                    if h1_periodos.intersection(h2_periodos):
                        conflitos_encontrados += 1
                        print("\n" + "="*50)
                        print(f"CONFLITO {conflitos_encontrados} ENCONTRADO:")
                        print(f"Turma: {pelotao}, Semana: {h1.semana.nome}, Dia: {dia.capitalize()}")
                        print(f"  - Aula 1 (ID: {h1.id}): '{h1.disciplina.materia}', Períodos: {h1.periodo}-{h1.periodo + h1.duracao - 1}")
                        print(f"  - Aula 2 (ID: {h2.id}): '{h2.disciplina.materia}', Períodos: {h2.periodo}-{h2.periodo + h2.duracao - 1}")

                        # Lógica para decidir qual aula deletar no modo --apply
                        # Critério: manter a aula mais recente (maior ID)
                        if h1.id > h2.id:
                            ids_para_deletar.add(h2.id)
                            print(f"  > Decisão: Manter ID {h1.id}, marcar ID {h2.id} para exclusão.")
                        else:
                            ids_para_deletar.add(h1.id)
                            print(f"  > Decisão: Manter ID {h2.id}, marcar ID {h1.id} para exclusão.")
                        print("="*50)

        if conflitos_encontrados == 0:
            print("\nNenhum conflito de horário encontrado. O banco de dados está limpo!")
            return

        print(f"\nTotal de {len(ids_para_deletar)} aula(s) 'fantasma' identificada(s) para remoção.")

        if apply_changes:
            print("\n--- APLICANDO MUDANÇAS ---")
            if not ids_para_deletar:
                print("Nenhum registro para deletar.")
            else:
                try:
                    stmt = delete(Horario).where(Horario.id.in_(list(ids_para_deletar)))
                    result = db.session.execute(stmt)
                    db.session.commit()
                    print(f"\nSUCESSO: {result.rowcount} registro(s) de aulas fantasmas foram removidos permanentemente.")
                except Exception as e:
                    db.session.rollback()
                    print(f"\nERRO: Falha ao tentar remover os registros do banco de dados: {e}")
        else:
            print("\n--- MODO DE DIAGNÓSTICO (DRY-RUN) ---")
            print("Nenhuma alteração foi feita no banco de dados.")
            print("Para remover as aulas fantasmas listadas acima, execute o script novamente com a opção --apply:")
            print("python -m backend.maintenance.find_schedule_conflicts --apply")


if __name__ == '__main__':
    find_conflicts()