from backend.app import create_app
from backend.models.database import db
from sqlalchemy import text, inspect

app = create_app()

with app.app_context():
    print("\n" + "="*60)
    print("DIAGNÓSTICO DE ESTRUTURA (SOMENTE LEITURA - SEM ALTERAÇÕES)")
    print("="*60)
    
    # Conecta ao banco apenas para inspecionar metadados
    inspector = inspect(db.engine)
    all_tables = inspector.get_table_names()

    # 1. VERIFICAR VERSÃO DO MIGRATION (O que o sistema ACHA que tem)
    print("\n1. STATUS DO CONTROLE DE VERSÃO (ALEMBIC):")
    try:
        version = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar()
        print(f"   Versão registrada no banco: {version}")
        
        # Análise rápida baseada nos arquivos que você enviou
        if version == '7a2463fe5fcb':
            print("   -> O sistema acha que a tabela de disciplina JÁ EXISTE.")
        elif version == '2b5b88901a2f':
            print("   -> O sistema acha que está na versão ANTERIOR à disciplina.")
        else:
            print(f"   -> Versão desconhecida ou intermediária.")
    except Exception as e:
        print(f"   ERRO: Não foi possível ler a tabela de versão. ({str(e)})")

    # 2. VERIFICAR TABELA DE REGRAS (O que REALMENTE existe)
    print("\n2. VERIFICAÇÃO DA TABELA 'discipline_rules':")
    if 'discipline_rules' in all_tables:
        print("   [OK] A tabela EXISTE fisicamente no banco.")
        # Opcional: contar registros
        qtd = db.session.execute(text("SELECT COUNT(*) FROM discipline_rules")).scalar()
        print(f"   -> Contém {qtd} registros.")
    else:
        print("   [FALTA] A tabela NÃO EXISTE. (Isso causa o erro de carregamento!)")

    # 3. VERIFICAR COLUNA EM SCHOOLS
    print("\n3. VERIFICAÇÃO DA COLUNA 'npccal_type' EM 'schools':")
    if 'schools' in all_tables:
        columns = [c['name'] for c in inspector.get_columns('schools')]
        if 'npccal_type' in columns:
            print("   [OK] A coluna 'npccal_type' EXISTE.")
        else:
            print("   [FALTA] A coluna 'npccal_type' NÃO EXISTE na tabela schools.")
    else:
        print("   [ERRO CRÍTICO] A tabela 'schools' não foi encontrada!")

    print("\n" + "="*60)
    print("CONCLUSÃO:")
    if 'discipline_rules' not in all_tables:
        print("O erro ocorre porque a tabela 'discipline_rules' não foi criada,")
        print("mas o código Python está tentando acessá-la.")
    elif 'schools' in all_tables and 'npccal_type' not in columns:
         print("O erro ocorre porque falta a coluna 'npccal_type' na tabela schools.")
    else:
        print("A estrutura parece correta. O problema pode ser nos dados (conteúdo nulo).")
    print("="*60 + "\n")