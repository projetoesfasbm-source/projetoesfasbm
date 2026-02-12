import sys
import os
from sqlalchemy import text

sys.path.append(os.getcwd())

try:
    from backend.app import create_app, db
except ImportError as e:
    print(f"❌ Erro de importação: {e}")
    sys.exit(1)

app = create_app()

def run_final_audit():
    print("="*80)
    print("DIAGNÓSTICO FINAL V3: LOCALIZAÇÃO DE DADOS PERDIDOS")
    print("="*80)

    with app.app_context():
        conn = db.session.connection()

        # 1. VERIFICAR SE A 3ª ESCOLA EXISTE NO BANCO
        print("\n[1] LISTAGEM GERAL DE ESCOLAS CADASTRADAS (Tabela 'schools')")
        print("Verifique se a escola que falta aparece aqui:")
        print(f"{'ID':<5} | {'Nome da Escola'}")
        print("-" * 60)
        
        try:
            # Busca todas as escolas, independente de terem processos
            sql_all_schools = text("SELECT id, nome FROM schools")
            schools = conn.execute(sql_all_schools).fetchall()
            
            school_ids = []
            for s in schools:
                print(f"{s[0]:<5} | {s[1]}")
                school_ids.append(s[0])
                
            if not schools:
                print("❌ CRÍTICO: Tabela 'schools' está vazia!")
        except Exception as e:
            print(f"❌ Erro ao ler escolas: {e}")

        # 2. CONTAGEM DE ALUNOS POR ESCOLA
        print("\n[2] TOTAL DE ALUNOS ATIVOS POR ESCOLA")
        print("Isso revela se a escola existe mas ficou sem alunos.")
        print(f"{'Escola':<40} | {'Qtd Alunos'}")
        print("-" * 60)
        
        try:
            sql_alunos_escola = text("""
                SELECT 
                    COALESCE(s.nome, 'SEM ESCOLA (ÓRFÃO)') as escola,
                    COUNT(a.id) as total
                FROM alunos a
                LEFT JOIN turmas t ON a.turma_id = t.id
                LEFT JOIN schools s ON t.school_id = s.id
                GROUP BY s.nome
                ORDER BY total DESC
            """)
            alunos_count = conn.execute(sql_alunos_escola).fetchall()
            for row in alunos_count:
                print(f"{str(row[0])[:40]:<40} | {row[1]}")
        except Exception as e:
            print(f"❌ Erro ao contar alunos: {e}")

        # 3. IDENTIFICAR OS 3 PROCESSOS TRAVADOS (Query Corrigida: t.nome)
        print("\n[3] ALUNOS COM PROCESSOS TRAVADOS (Status Vazio - Botões Sumidos)")
        print(f"{'ID Proc.':<10} | {'Aluno':<30} | {'Turma':<20}")
        print("-" * 70)

        try:
            sql_bugados = text("""
                SELECT 
                    p.id, 
                    COALESCE(u.nome_completo, 'USUÁRIO DELETADO') as nome,
                    COALESCE(t.nome, 'SEM TURMA') as turma
                FROM processos_disciplina p
                LEFT JOIN alunos a ON p.aluno_id = a.id
                LEFT JOIN users u ON a.user_id = u.id  
                LEFT JOIN turmas t ON a.turma_id = t.id
                WHERE p.status IS NULL OR p.status = ''
            """)
            
            bugados = conn.execute(sql_bugados).fetchall()
            
            if not bugados:
                print("✅ Nenhum processo travado encontrado.")
            
            for row in bugados:
                pid = row[0]
                nome = row[1] if row[1] else "Desconhecido"
                turma = row[2] if row[2] else "N/A"
                print(f"{pid:<10} | {nome[:30]:<30} | {turma[:20]:<20}")
                
        except Exception as e:
            print(f"❌ Erro na query dos travados: {e}")

    print("\n" + "="*80)

if __name__ == "__main__":
    run_final_audit()