from backend.app import create_app, db
from sqlalchemy import text

app = create_app()

def verificar_e_corrigir():
    print("Iniciando verificação de colunas...")
    with app.app_context():
        conn = db.session.connection()
        
        # 1. Lista de colunas necessárias para o novo fluxo
        colunas_novas = [
            ("data_notificacao_decisao", "DATETIME"),
            ("texto_recurso", "TEXT"),
            ("data_recurso", "DATETIME"),
            ("decisao_recurso", "VARCHAR(50)"),
            ("fundamentacao_recurso", "TEXT"),
            ("autoridade_recurso_id", "INTEGER"),
            ("data_julgamento_recurso", "DATETIME"),
            ("ciente_aluno", "BOOLEAN DEFAULT 0") # Garante que essa existe
        ]

        for col, tipo in colunas_novas:
            try:
                # Tenta adicionar. Se der erro, é pq já existe (o que é bom)
                sql = text(f"ALTER TABLE processos_disciplina ADD COLUMN {col} {tipo}")
                conn.execute(sql)
                print(f"✅ Coluna '{col}' adicionada com sucesso.")
            except Exception as e:
                # Se o erro for "Duplicate column name", ignoramos. Se for outro, mostramos.
                if "Duplicate column name" in str(e):
                    print(f"🆗 Coluna '{col}' já existe.")
                else:
                    print(f"⚠️ Aviso sobre '{col}': {e}")

        db.session.commit()
        print("Verificação concluída. Reinicie o site (Reload).")

if __name__ == "__main__":
    verificar_e_corrigir()