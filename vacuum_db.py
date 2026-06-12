import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys

db_url = "postgresql://sisgem_user:7HmEGEXbmfG3UNV1GKbhSIXftyvJbAdB@dpg-d8f16u58nd3s73ferp60-a.oregon-postgres.render.com/sisgem?sslmode=require"

try:
    print("Conectando ao banco de dados...")
    conn = psycopg2.connect(db_url)
    
    # VACUUM needs autocommit to be true
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    
    cur = conn.cursor()
    print("Executando VACUUM ANALYZE...")
    cur.execute("VACUUM ANALYZE;")
    print("VACUUM ANALYZE concluído com sucesso!")
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"Erro: {e}")
