import os
import sys
sys.path.append(os.getcwd())
from backend.app import create_app
from backend.models.database import db
from backend.models.horario import Horario
from backend.models.semana import Semana
from backend.models.ciclo import Ciclo
from backend.models.school import School
from backend.models.disciplina import Disciplina

app = create_app()
with app.app_context():
    print("Gerando Relatório de Conferência Organizado e Sequencial...")
    
    # Busca os dados cruzados e ordena temporalmente
    query = (
        db.session.query(Horario, Semana, Ciclo, School)
        .join(Semana, Horario.semana_id == Semana.id)
        .join(Ciclo, Semana.ciclo_id == Ciclo.id)
        .join(School, Ciclo.school_id == School.id)
        .order_by(
            School.nome, 
            Ciclo.nome, 
            Semana.id, 
            Horario.pelotao, 
            Horario.dia_semana, 
            Horario.periodo
        )
    ).all()
    
    with open('RESTAURACAO_ORGANIZADA.txt', 'w', encoding='utf-8') as f:
        # Cabeçalho estruturado
        header = (f"{'ESCOLA':<25} | {'CICLO':<15} | {'SEMANA':<12} | "
                  f"{'TURMA':<25} | {'DIA':<8} | {'PER':<3} | {'MATÉRIA'}\n")
        f.write(header)
        f.write("-" * len(header) + "\n")
        
        for h, sem, cic, sch in query:
            # Busca a disciplina (tentando 'nome' ou 'materia')
            disc = db.session.get(Disciplina, h.disciplina_id)
            if disc:
                # Tenta pegar o nome da matéria independente de como a coluna se chama
                nome_materia = getattr(disc, 'nome', getattr(disc, 'materia', 'Sem Nome'))
            else:
                nome_materia = "N/A"
            
            linha = (
                f"{sch.nome[:25]:<25} | "
                f"{cic.nome[:15]:<15} | "
                f"{sem.nome[:12]:<12} | "
                f"{h.pelotao[:25]:<25} | "
                f"{h.dia_semana[:8]:<8} | "
                f"{h.periodo:<3} | "
                f"{nome_materia}\n"
            )
            f.write(linha)
            
    print(f"\n[SUCESSO] Relatório gerado: 'RESTAURACAO_ORGANIZADA.txt'")
    print(f"Total de {len(query)} períodos organizados em sequência.")