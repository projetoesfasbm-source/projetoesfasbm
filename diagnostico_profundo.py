import sys
import os
from sqlalchemy import text

sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
from backend.models.turma import Turma
from backend.models.disciplina import Disciplina
from backend.models.diario_classe import DiarioClasse

app = create_app()

def diagnosticar_profundo():
    with app.app_context():
        print("\n" + "="*80)
        print("DIAGNÓSTICO PROFUNDO DE CARGA HORÁRIA")
        print("="*80)

        # 1. Buscar TODAS as turmas que podem ser a "Turma 8"
        turmas_candidatas = db.session.query(Turma).filter(Turma.nome.like('%8%')).all()
        
        print(f"Turmas encontradas com '8' no nome: {len(turmas_candidatas)}")
        for t in turmas_candidatas:
            print(f" - ID: {t.id} | Nome: {t.nome} | Escola ID: {t.school_id}")

        print("-" * 80)

        # 2. Buscar TODAS as disciplinas que contenham os termos chave
        # Isso pega duplicatas e variações de nome
        termos = ['Administração', 'AMT', 'Decisão de tiro', 'Operações']
        disciplinas_candidatas = []
        for termo in termos:
            res = db.session.query(Disciplina).filter(Disciplina.materia.like(f'%{termo}%')).all()
            disciplinas_candidatas.extend(res)
        
        # Remove duplicatas da lista (pelo ID)
        disciplinas_unicas = {d.id: d for d in disciplinas_candidatas}.values()
        
        print(f"Disciplinas candidatas encontradas: {len(disciplinas_unicas)}")
        print("-" * 80)
        print("VARRENDO BANCO DE DADOS POR REGISTROS...")

        encontrou_algo = False

        # 3. Cruzamento: Verifica onde existem registros de diário
        for turma in turmas_candidatas:
            for disc in disciplinas_unicas:
                
                # Busca diários para essa combinação específica
                diarios = db.session.query(DiarioClasse).filter_by(
                    turma_id=turma.id,
                    disciplina_id=disc.id
                ).order_by(DiarioClasse.data_aula, DiarioClasse.periodo, DiarioClasse.id).all()
                
                qtd = len(diarios)
                
                # Só mostra se tiver registros (para não poluir a tela)
                if qtd > 0:
                    encontrou_algo = True
                    print(f"\n>>> ALVO LOCALIZADO!")
                    print(f"TURMA: {turma.nome} (ID: {turma.id})")
                    print(f"DISCIPLINA: {disc.materia} (ID: {disc.id})")
                    print(f"CARGA HORÁRIA REGISTRADA: {qtd} aulas")
                    print(f"CARGA PREVISTA: {disc.carga_horaria_prevista}h")
                    
                    print(f"{'ID':<6} | {'DATA':<12} | {'PERIODO':<8} | {'INSTRUTOR'}")
                    print("-" * 60)
                    
                    datas_vistas = {}
                    
                    for d in diarios:
                        data_str = d.data_aula.strftime('%d/%m/%Y')
                        periodo_str = str(d.periodo) if d.periodo is not None else "NULL"
                        
                        nome_instrutor = "---"
                        if d.responsavel:
                            nome_instrutor = d.responsavel.nome_de_guerra or "Sem Guerra"

                        # Check simples de duplicidade visual
                        chave = f"{data_str}-{periodo_str}"
                        aviso = ""
                        if chave in datas_vistas and periodo_str != "NULL":
                            aviso = " <--- DUPLICADO?"
                        datas_vistas[chave] = True

                        print(f"{d.id:<6} | {data_str:<12} | {periodo_str:<8} | {nome_instrutor}{aviso}")

        if not encontrou_algo:
            print("\nNENHUM registro de aula encontrado para as combinações pesquisadas.")
            print("Dica: Verifique se os nomes 'Administração' ou 'AMT' estão corretos no banco.")

        print("\n" + "="*80)

if __name__ == "__main__":
    diagnosticar_profundo()