import sys
import os
from sqlalchemy import text

# Adiciona o diretório atual ao path para importar o backend
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
from backend.models.turma import Turma
from backend.models.disciplina import Disciplina
from backend.models.diario_classe import DiarioClasse
from backend.models.user import User

app = create_app()

def diagnosticar():
    with app.app_context():
        print("="*80)
        print("DIAGNÓSTICO DE CARGA HORÁRIA - TURMA 8")
        print("="*80)

        # 1. Localizar a Turma 8
        # Tenta achar por nome exato ou contenha "8"
        turma = db.session.query(Turma).filter(Turma.nome.like('%8%')).first()
        
        if not turma:
            print("ERRO: Turma 8 não encontrada no banco de dados.")
            return
        
        print(f"Turma identificada: ID {turma.id} - Nome: {turma.nome}")
        print("-" * 80)

        # Lista de disciplinas problemáticas (buscando por parte do nome para garantir match)
        alvos = [
            "Administração Pública", 
            "AMT - I"
        ]

        for termo in alvos:
            disciplina = db.session.query(Disciplina).filter(Disciplina.materia.like(f"%{termo}%")).first()
            
            if not disciplina:
                print(f"AVISO: Disciplina com termo '{termo}' não encontrada.")
                continue

            print(f"\n>>> ANALISANDO: {disciplina.materia} (ID: {disciplina.id})")
            print(f"Carga Horária Prevista: {disciplina.carga_horaria_prevista}h")
            
            # Buscar todos os diários dessa combinação
            diarios = db.session.query(DiarioClasse).filter_by(
                turma_id=turma.id, 
                disciplina_id=disciplina.id
            ).order_by(DiarioClasse.data_aula, DiarioClasse.periodo, DiarioClasse.id).all()

            total_registrado = len(diarios)
            print(f"Total de Aulas Registradas (Diários): {total_registrado}")
            
            if total_registrado == 0:
                print("Nenhum registro encontrado.")
            else:
                print(f"\n{'ID':<6} | {'DATA':<12} | {'PERIODO':<8} | {'INSTRUTOR (ID)':<25} | {'CONTEÚDO (Início)'}")
                print("-" * 100)
                
                datas_vistas = {}
                
                for d in diarios:
                    # Tenta pegar nome do instrutor
                    instrutor_nome = "Desconhecido"
                    if d.responsavel:
                        instrutor_nome = d.responsavel.nome_de_guerra or d.responsavel.nome_completo
                        instrutor_nome = f"{instrutor_nome} ({d.responsavel_id})"

                    # Formatação de dados
                    data_str = d.data_aula.strftime('%d/%m/%Y')
                    periodo_str = str(d.periodo) if d.periodo is not None else "NULL"
                    conteudo_resumo = (d.conteudo_ministrado[:40] + '...') if d.conteudo_ministrado else "---"

                    # Checagem de DUPLICIDADE ÓBVIA (Mesma data e mesmo período)
                    chave_duplicidade = f"{data_str}-{periodo_str}"
                    marcador = ""
                    if chave_duplicidade in datas_vistas and periodo_str != "NULL":
                        marcador = " <--- POSSÍVEL DUPLICATA!"
                    datas_vistas[chave_duplicidade] = True

                    print(f"{d.id:<6} | {data_str:<12} | {periodo_str:<8} | {instrutor_nome:<25} | {conteudo_resumo}{marcador}")

        print("\n" + "="*80)
        print("FIM DO DIAGNÓSTICO")

if __name__ == "__main__":
    diagnosticar()