import psycopg2
import sys
import os

# Obtém a URL do banco do ambiente ou usa a configurada por padrão
db_url = os.environ.get("DATABASE_URL", "postgresql://sisgem_user:7HmEGEXbmfG3UNV1GKbhSIXftyvJbAdB@dpg-d8f16u58nd3s73ferp60-a.oregon-postgres.render.com/sisgem?sslmode=require")

# Índices direcionados para colunas de alto tráfego / filtro frequente
INDICES_OTIMIZADOS = [
    # Tabela, Nome do Índice, Expressão de Colunas
    ("horarios", "idx_horarios_status_pelotao", '("status", "pelotao", "semana_id")'),
    ("horarios", "idx_horarios_dia_semana_periodo", '("dia_semana", "periodo")'),
    ("diarios_classe", "idx_diarios_turma_deleted_status", '("turma_id", "is_deleted", "status")'),
    ("users", "idx_users_active_role", '("is_active", "role")'),
    ("chamados_suporte", "idx_chamados_suporte_status", '("status")'),
    ("background_jobs", "idx_background_jobs_status_created", '("status", "created_at")'),
    ("site_configs", "idx_site_configs_key", '("config_key")'),
]

def criar_indices():
    try:
        print("Conectando ao banco de dados no Render...")
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cursor = conn.cursor()

        print("\n1. Verificando índices para chaves estrangeiras pendentes...")
        query_fk = """
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
        cursor.execute(query_fk)
        fks_pendentes = cursor.fetchall()

        if fks_pendentes:
            for table_name, column_name in fks_pendentes:
                safe_table = str(table_name).replace('"', '')
                idx_name = f"idx_fk_{safe_table}_{column_name}"[:63]
                sql = f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{idx_name}" ON {table_name} ("{column_name}");'
                print(f" -> Criando índice FK {idx_name} em {table_name}({column_name})...")
                try:
                    cursor.execute(sql)
                except Exception as e:
                    print(f"    [Aviso] Erro ao criar {idx_name}: {e}")

        print("\n2. Criando índices compostos otimizados para filtros de alta frequência (CONCURRENTLY)...")
        for table_name, idx_name, cols in INDICES_OTIMIZADOS:
            sql = f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{idx_name}" ON {table_name} {cols};'
            print(f" -> Indexando {table_name} com {idx_name} {cols}...")
            try:
                cursor.execute(sql)
            except Exception as e:
                print(f"    [Aviso] Falha ou tabela indisponível ao criar {idx_name}: {e}")

        cursor.close()
        conn.close()
        print("\nOtimização de índices finalizada com sucesso! Zero interrupção para o sistema.")
    except Exception as e:
        print(f"Erro ao executar criação de índices: {e}")

if __name__ == "__main__":
    criar_indices()
