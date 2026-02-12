import sys
import os
from sqlalchemy import text, inspect

# Adiciona o diretório atual ao path
sys.path.append(os.getcwd())

try:
    from backend.app import create_app, db
    # Não importamos os modelos diretamente para evitar erros de ORM em dados quebrados
except ImportError as e:
    print(f"❌ Erro de importação: {e}")
    sys.exit(1)

app = create_app()

def run_production_check():
    print("="*60)
    print("DIAGNÓSTICO CIRÚRGICO - SISTEMA EM PRODUÇÃO")
    print("="*60)

    with app.app_context():
        inspector = inspect(db.engine)
        conn = db.session.connection()

        # 1. VERIFICAÇÃO DE COLUNAS (Essencial para saber se a migração funcionou)
        print("\n[1] ESTRUTURA DA TABELA 'processos_disciplina'")
        columns = {col['name'] for col in inspector.get_columns('processos_disciplina')}
        required_cols = ['fundamentacao', 'observacao_decisao', 'detalhes_sancao', 'status']
        
        missing = [c for c in required_cols if c not in columns]
        if missing:
            print(f"❌ CRÍTICO: Colunas faltando no banco: {missing}")
            print("   -> Isso quebra o sistema imediatamente ao tentar salvar/ler.")
        else:
            print("✅ Estrutura de colunas OK.")

        # 2. ANÁLISE DE STATUS (Causa provável do sumiço dos botões)
        print("\n[2] CONTAGEM POR STATUS (Impacta visibilidade dos botões)")
        # Trazemos também se o status é NULL ou Vazio
        sql_status = text("""
            SELECT 
                COALESCE(status, 'NULL_OU_VAZIO') as st, 
                COUNT(*) as qtd 
            FROM processos_disciplina 
            GROUP BY status
        """)
        results = conn.execute(sql_status).fetchall()
        
        print(f"{'STATUS':<30} | {'QTD':<5}")
        print("-" * 40)
        total_sem_status = 0
        for row in results:
            status_val = row[0]
            if status_val == '' or status_val == 'NULL_OU_VAZIO':
                total_sem_status += row[1]
            print(f"{str(status_val):<30} | {row[1]:<5}")
        
        if total_sem_status > 0:
            print(f"\n❌ ALERTA: {total_sem_status} processos estão sem STATUS definido.")
            print("   -> Nestes casos, o botão de análise NÃO VAI APARECER.")

        # 3. ANÁLISE DE VÍNCULOS (Órfãos)
        print("\n[3] DADOS ÓRFÃOS (Punições sem Aluno/Instrutor cadastrado)")
        print("   -> O sistema pode estar falhando ao tentar buscar o nome do aluno.")
        
        # Processos onde o ID do aluno não existe na tabela alunos
        sql_orphans = text("""
            SELECT count(*) 
            FROM processos_disciplina p 
            LEFT JOIN alunos a ON p.aluno_id = a.id 
            WHERE a.id IS NULL
        """)
        orphans = conn.execute(sql_orphans).scalar()
        
        print(f"ℹ️  Processos apontando para Alunos inexistentes: {orphans}")
        
        if orphans > 0:
            print("   ⚠️  ATENÇÃO: Se o código HTML tentar fazer `processo.aluno.nome`, o sistema trava ou não renderiza o botão.")

        # 4. TESTE DE DADOS NULLOS CRÍTICOS
        print("\n[4] VERIFICAÇÃO DE DADOS NULOS EM CAMPOS OBRIGATÓRIOS")
        # Verifica se tem processo sem relator ou sem fato (quebra a tela)
        sql_nulls = text("""
            SELECT count(*) FROM processos_disciplina 
            WHERE fato_constatado IS NULL OR relator_id IS NULL
        """)
        critical_nulls = conn.execute(sql_nulls).scalar()
        
        if critical_nulls > 0:
            print(f"❌ CRÍTICO: {critical_nulls} processos com 'fato_constatado' ou 'relator' NULOS.")
        else:
            print("✅ Dados obrigatórios preenchidos.")

    print("\n" + "="*60)

if __name__ == "__main__":
    run_production_check()