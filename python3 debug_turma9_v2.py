from backend.app import create_app
from backend.models.database import db
from backend.models.turma import Turma
from backend.models.disciplina_turma import DisciplinaTurma
from backend.models.diario_classe import DiarioClasse
from sqlalchemy import select, func

app = create_app()

with app.app_context():
    print("--- DIAGNÓSTICO TURMA 9 (VERSÃO 2) ---\n")

    # 1. Tentar encontrar turmas com "9" no nome
    turmas = db.session.scalars(select(Turma).where(Turma.nome.ilike('%9%'))).all()
    
    if not turmas:
        print("ERRO CRÍTICO: Nenhuma turma com '9' no nome encontrada.")
    else:
        for t in turmas:
            print(f"TURMA ENCONTRADA: ID={t.id} | Nome='{t.nome}'")
            
            # 2. Verificar Diários dessa Turma
            num_diarios = db.session.scalar(select(func.count(DiarioClasse.id)).where(DiarioClasse.turma_id == t.id))
            print(f"   -> Quantidade de Diários lançados: {num_diarios}")
            
            if num_diarios > 0:
                # 3. Verificar vínculos usando o NOME exato
                vinculos_nome = db.session.scalars(select(DisciplinaTurma).where(DisciplinaTurma.pelotao == t.nome)).all()
                print(f"   -> Vínculos (DisciplinaTurma) onde pelotao='{t.nome}': {len(vinculos_nome)}")
                
                # 4. Se não achar vínculos exatos, procurar parecidos
                if len(vinculos_nome) == 0:
                    print("   [!] ALERTA: Esta turma tem diários, mas NENHUM instrutor vinculado com esse nome exato!")
                    
                    # Procura o que tem no banco parecido com "9"
                    parecidos = db.session.scalars(select(DisciplinaTurma.pelotao).where(DisciplinaTurma.pelotao.ilike('%9%')).distinct()).all()
                    print(f"   [?] Nomes encontrados na tabela de vínculos (disciplina_turmas): {parecidos}")
                    print(f"   [DICA] Provavelmente você precisa renomear a turma '{t.nome}' para um dos nomes acima.")

    print("\n--- FIM DO DIAGNÓSTICO ---")