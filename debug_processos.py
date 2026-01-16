import sys
import os
from sqlalchemy import select, text

sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
from backend.models.processo_disciplina import ProcessoDisciplina
from backend.models.aluno import Aluno
from backend.models.turma import Turma
from backend.models.school import School

app = create_app()

def diagnosticar():
    with app.app_context():
        print("="*60)
        print("DIAGNÓSTICO DE PROCESSOS - DADOS REAIS")
        print("="*60)

        # 1. Total Geral
        total = db.session.scalar(select(db.func.count(ProcessoDisciplina.id)))
        print(f"1. Total de Processos no Banco: {total}")

        if total == 0:
            print("   [CRÍTICO] Tabela de processos está vazia.")
            return

        # 2. Verificar Escolas e Tipos
        print("\n2. Escolas Cadastradas:")
        escolas = db.session.scalars(select(School)).all()
        ctsp_id = None
        for e in escolas:
            print(f"   - ID: {e.id} | Nome: {e.nome} | Tipo: {e.npccal_type}")
            if e.npccal_type and 'ctsp' in e.npccal_type.lower():
                ctsp_id = e.id

        if not ctsp_id:
            print("   [AVISO] Nenhuma escola marcada explicitamente como 'ctsp' no banco.")
        else:
            print(f"   > ID da Escola CTSP identificada: {ctsp_id}")

        # 3. Investigação do 'Sumiço' (Query manual)
        print("\n3. Teste de Relacionamento (Processo -> Aluno -> Turma -> Escola)")
        
        # Pega os 5 últimos processos para analisar
        amostra = db.session.scalars(
            select(ProcessoDisciplina)
            .order_by(ProcessoDisciplina.id.desc())
            .limit(5)
        ).all()

        for p in amostra:
            aluno = db.session.get(Aluno, p.aluno_id)
            turma = db.session.get(Turma, aluno.turma_id) if aluno and aluno.turma_id else None
            escola_id = turma.school_id if turma else "SEM TURMA"
            
            print(f"   Processo #{p.id} | Aluno: {aluno.user.nome_completo if aluno else 'N/A'}")
            print(f"     -> Turma ID: {aluno.turma_id if aluno else 'N/A'} | Escola ID: {escola_id}")
            
            if escola_id == "SEM TURMA":
                print("     [ERRO IDENTIFICADO] Aluno sem turma vinculada. O filtro 'Turma.school_id' esconde este processo.")
            elif ctsp_id and escola_id != ctsp_id:
                print(f"     [INFO] Processo pertence à escola {escola_id}, não à escola CTSP ({ctsp_id}).")
            else:
                print("     [OK] Relacionamento parece correto. Verifique status.")

if __name__ == "__main__":
    diagnosticar()