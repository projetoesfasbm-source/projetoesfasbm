import sys
import os
from sqlalchemy import text

# Adiciona o diretório atual ao caminho para encontrar o backend
sys.path.append(os.getcwd())

try:
    from backend.app import create_app, db
except ImportError as e:
    print(f"❌ Erro crítico de importação: {e}")
    print("Verifique se você está executando este script na raiz do projeto.")
    sys.exit(1)

app = create_app()

def fix_buttons_now():
    print("="*60)
    print("REPARO DE STATUS - CORREÇÃO DOS BOTÕES")
    print("="*60)

    with app.app_context():
        conn = db.session.connection()
        
        # 1. Diagnóstico: Quantos estão com problema?
        sql_check = text("SELECT count(*) FROM processos_disciplina WHERE status IS NULL OR status = ''")
        qtd_problematicos = conn.execute(sql_check).scalar()
        
        print(f"🔎 Processos com status vazio (Botões sumidos): {qtd_problematicos}")

        if qtd_problematicos > 0:
            print("🔧 Aplicando correção...")
            
            # 2. Correção: Define status padrão para destravar o fluxo
            sql_update = text("""
                UPDATE processos_disciplina 
                SET status = 'AGUARDANDO_CIENCIA' 
                WHERE status IS NULL OR status = ''
            """)
            
            result = conn.execute(sql_update)
            db.session.commit()
            
            print(f"✅ SUCESSO: {result.rowcount} processos foram recuperados.")
            print("   -> Volte ao sistema e recarregue a página.")
            print("   -> Os botões de 'Dar Ciência' ou 'Analisar' devem aparecer agora.")
        else:
            print("✅ Tudo limpo. Não existem processos com status vazio no banco.")

    print("="*60)

if __name__ == "__main__":
    fix_buttons_now()