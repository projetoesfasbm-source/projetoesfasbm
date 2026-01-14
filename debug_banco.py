from backend.app import create_app
from backend.models.database import db
from backend.models.processo_disciplina import ProcessoDisciplina
from backend.models.aluno import Aluno
from backend.models.turma import Turma
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("\n" + "="*40)
    print("DIAGNÓSTICO DE DADOS - JUSTIÇA")
    print("="*40)

    # 1. Contagem Bruta
    total = db.session.scalar(text("SELECT COUNT(*) FROM processos_disciplina"))
    print(f"1. Total de Processos no Banco (SQL Puro): {total}")

    if total == 0:
        print("   ERRO GRAVE: A tabela está vazia! Dados foram deletados ou banco errado.")
        exit()

    # 2. Verificando Vínculos (A causa provável)
    print("\n2. Verificando Integridade dos Vínculos:")
    
    # Processos onde o aluno não existe
    orphans = db.session.execute(text("""
        SELECT COUNT(*) FROM processos_disciplina p 
        LEFT JOIN alunos a ON p.aluno_id = a.id 
        WHERE a.id IS NULL
    """)).scalar()
    print(f"   - Processos com Aluno INEXISTENTE: {orphans}")

    # Processos onde o aluno existe, mas NÃO TEM TURMA
    no_class = db.session.execute(text("""
        SELECT COUNT(*) FROM processos_disciplina p 
        JOIN alunos a ON p.aluno_id = a.id 
        WHERE a.turma_id IS NULL
    """)).scalar()
    print(f"   - Processos de Alunos SEM TURMA: {no_class} (Esses somem com Inner Join!)")

    # 3. Listagem de Amostra (O que deveria aparecer)
    print("\n3. Amostra de Processos (Top 5):")
    procs = db.session.query(ProcessoDisciplina).limit(5).all()
    for p in procs:
        a_nome = p.aluno.user.nome_completo if p.aluno and p.aluno.user else "SEM ALUNO"
        t_nome = p.aluno.turma.nome if p.aluno and p.aluno.turma else "SEM TURMA"
        s_id = p.aluno.turma.school_id if p.aluno and p.aluno.turma else "N/A"
        print(f"   ID: {p.id} | Aluno: {a_nome} | Turma: {t_nome} | School_ID da Turma: {s_id}")

    print("="*40 + "\n")