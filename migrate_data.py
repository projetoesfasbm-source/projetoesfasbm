import sys
from sqlalchemy import create_engine, MetaData, text

def migrate_data():
    print("="*50)
    print("   MIGRAÇÃO DE DADOS: MySQL -> PostgreSQL")
    print("="*50)
    
    if len(sys.argv) == 3:
        source_url = sys.argv[1]
        target_url = sys.argv[2]
    else:
        print("\n1. Obtenha a URL do banco MySQL (PythonAnywhere)")
        print("   Ex: mysql+pymysql://user:senha@host/banco")
        source_url = input("URL de Origem (MySQL): ").strip()
        
        print("\n2. Obtenha a External Database URL do banco PostgreSQL (Render)")
        print("   Ex: postgresql://user:senha@host/banco")
        target_url = input("URL de Destino (PostgreSQL): ").strip()

    if not source_url or not target_url:
        print("Erro: As duas URLs são obrigatórias!")
        sys.exit(1)

    # Correção comum de prefixo
    if target_url.startswith("postgres://"):
        target_url = target_url.replace("postgres://", "postgresql://", 1)
        
    print("\nConectando aos bancos de dados...")
    try:
        source_engine = create_engine(source_url)
        target_engine = create_engine(target_url)
        
        with source_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        with target_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        print(f"Erro ao conectar: {e}")
        sys.exit(1)

    print("Conexões estabelecidas com sucesso!\n")
    
    print("Mapeando tabelas do banco de dados antigo (Origem)...")
    source_metadata = MetaData()
    source_metadata.reflect(bind=source_engine)

    print("Mapeando tabelas do banco de dados novo (Destino)...")
    target_metadata = MetaData()
    target_metadata.reflect(bind=target_engine)

    # Ordena as tabelas respeitando as chaves estrangeiras
    tables = target_metadata.sorted_tables

    print("\nIniciando transferência segura de dados...")
    
    with target_engine.begin() as target_conn:
        with source_engine.connect() as source_conn:
            
            for table in tables:
                table_name = table.name
                
                if table_name == 'alembic_version':
                    continue
                
                print(f"Lendo: {table_name}...", end=" ")
                try:
                    # Usa a tabela de origem para evitar conflito de dialeto (MySQL x PostgreSQL)
                    source_table = source_metadata.tables[table_name]
                    result = source_conn.execute(source_table.select())
                    rows = result.fetchall()
                    
                    if not rows:
                        print("Vazia. Pulando.")
                        continue
                        
                    dicts = []
                    for row in rows:
                        try:
                            dicts.append(dict(row._mapping))
                        except AttributeError:
                            dicts.append(dict(row))
                    
                    print(f"[{len(dicts)} registros] -> Injetando...", end=" ")
                    
                    # Limpa a tabela caso já tenha algo (por precaução)
                    target_conn.execute(table.delete())
                    
                    # Insere todos os dados
                    target_conn.execute(table.insert(), dicts)
                    print("OK!", end=" ")
                    
                    # Atualiza a contagem do Auto-Increment (Sequence) no PostgreSQL
                    if 'id' in table.columns and str(table.columns['id'].type) in ['INTEGER', 'BIGINT', 'SMALLINT']:
                        seq_query = text(f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), coalesce(max(id), 1), max(id) IS NOT null) FROM {table_name};")
                        try:
                            target_conn.execute(seq_query)
                            print("(Sequence Atualizada)")
                        except Exception as seq_err:
                            print(f"(Aviso Sequence: {seq_err})")
                    else:
                        print()
                            
                except Exception as e:
                    print(f"\n[ERRO] Falha na tabela {table_name}: {e}")
                    print("Cancelando todas as alterações (Rollback de segurança)...")
                    raise e
                    
    print("\n" + "="*50)
    print("   MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
    print("   Todos os dados agora moram no Render!")
    print("="*50)

if __name__ == "__main__":
    migrate_data()
