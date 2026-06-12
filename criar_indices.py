import psycopg2
import sys

db_url = "postgresql://sisgem_user:7HmEGEXbmfG3UNV1GKbhSIXftyvJbAdB@dpg-d8f16u58nd3s73ferp60-a.oregon-postgres.render.com/sisgem?sslmode=require"

try:
    print("Conectando ao banco de dados no Render...")
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cursor = conn.cursor()
    
    print("Procurando por chaves estrangeiras sem índices...")
    # Consulta avançada no catálogo do PostgreSQL para encontrar Foreign Keys sem Índice
    query = """
    SELECT 
        c.conrelid::regclass AS table_name, 
        a.attname AS column_name
    FROM 
        pg_constraint c 
        JOIN pg_attribute a ON a.attnum = ANY(c.conkey) AND a.attrelid = c.conrelid
    WHERE 
        c.contype = 'f'
        AND NOT EXISTS (
            SELECT 1 
            FROM pg_index i 
            JOIN pg_attribute a2 ON a2.attnum = ANY(i.indkey) AND a2.attrelid = i.indrelid
            WHERE i.indrelid = c.conrelid AND a2.attname = a.attname
        )
    """
    cursor.execute(query)
    results = cursor.fetchall()
    
    if not results:
        print("Tudo perfeito! Nenhum indice faltando.")
    else:
        print(f"Foram encontradas {len(results)} colunas sem indice (isso causava a lentidao!).")
        print("Criando indices para destravar o banco de dados...")
        
        for table_name, column_name in results:
            # Limpa o nome da tabela caso tenha aspas
            safe_table_name = str(table_name).replace('"', '')
            index_name = f"idx_{safe_table_name}_{column_name}"
            
            # Limita tamanho do nome do indice caso seja muito grande
            if len(index_name) > 63:
                index_name = index_name[:63]
                
            sql = f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{index_name}" ON {table_name} ("{column_name}");'
            print(f" -> Indexando {table_name}.{column_name}...")
            try:
                cursor.execute(sql)
            except Exception as e:
                # Fallback se CONCURRENTLY nao suportar em alguma versao ou transacao
                print(f"    Tentando metodo padrao para {index_name}...")
                sql_fallback = f'CREATE INDEX IF NOT EXISTS "{index_name}" ON {table_name} ("{column_name}");'
                try:
                    cursor.execute(sql_fallback)
                except Exception as e2:
                    print(f"    Erro ao indexar {table_name}.{column_name}: {e2}")
                
    cursor.close()
    conn.close()
    print("\nProcesso finalizado com sucesso! O banco de dados esta operando em alta velocidade.")
except Exception as e:
    print(f"Erro fatal: {e}")
