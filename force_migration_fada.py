import sys
import os
from sqlalchemy import text, inspect, Float, DateTime, Text, Integer

# Setup do ambiente
sys.path.append(os.getcwd())
try:
    from backend.app import create_app
    app = create_app()
except ImportError:
    from backend.app import app

from backend.models.database import db

def forcar_fada():
    with app.app_context():
        print("="*50)
        print("VERIFICAÇÃO E CORREÇÃO: FADA & JUSTIÇA")
        print("="*50)
        
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()

        # 1. CRIAR TABELA FADA SE NÃO EXISTIR
        if 'fada_avaliacoes' not in tables:
            print(" > Tabela 'fada_avaliacoes' NÃO encontrada. Criando...")
            try:
                # SQL direto para criar a tabela conforme o modelo
                sql_create = text("""
                CREATE TABLE fada_avaliacoes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    aluno_id INT NOT NULL,
                    avaliador_id INT NOT NULL,
                    data_avaliacao DATETIME,
                    observacao TEXT,
                    expressao FLOAT DEFAULT 0.0,
                    planejamento FLOAT DEFAULT 0.0,
                    perseveranca FLOAT DEFAULT 0.0,
                    apresentacao FLOAT DEFAULT 0.0,
                    lealdade FLOAT DEFAULT 0.0,
                    tato FLOAT DEFAULT 0.0,
                    equilibrio FLOAT DEFAULT 0.0,
                    disciplina FLOAT DEFAULT 0.0,
                    responsabilidade FLOAT DEFAULT 0.0,
                    maturidade FLOAT DEFAULT 0.0,
                    assiduidade FLOAT DEFAULT 0.0,
                    pontualidade FLOAT DEFAULT 0.0,
                    diccao FLOAT DEFAULT 0.0,
                    lideranca FLOAT DEFAULT 0.0,
                    relacionamento FLOAT DEFAULT 0.0,
                    etica FLOAT DEFAULT 0.0,
                    produtividade FLOAT DEFAULT 0.0,
                    eficiencia FLOAT DEFAULT 0.0,
                    media_final FLOAT DEFAULT 0.0,
                    FOREIGN KEY(aluno_id) REFERENCES alunos(id),
                    FOREIGN KEY(avaliador_id) REFERENCES users(id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                with db.engine.connect() as conn:
                    conn.execute(sql_create)
                print("   [SUCESSO] Tabela 'fada_avaliacoes' criada.")
            except Exception as e:
                print(f"   [ERRO] Falha ao criar tabela: {e}")
        else:
            print(" > Tabela 'fada_avaliacoes' já existe. Verificando colunas...")
            # (Aqui poderíamos verificar colunas, mas vamos assumir que se existe está ok ou o script SQL acima resolveu)

        # 2. GARANTIR COLUNAS NOVAS EM PROCESSOS_DISCIPLINA
        # Caso o passo manual anterior tenha deixado algo para trás
        cols_processo = [c['name'] for c in inspector.get_columns('processos_disciplina')]
        novas_cols = {
            'is_crime': 'BOOLEAN DEFAULT 0',
            'tipo_sancao': 'VARCHAR(50)',
            'dias_sancao': 'INT',
            'origem_punicao': "VARCHAR(20) DEFAULT 'NPCCAL'"
        }
        
        with db.engine.connect() as conn:
            conn.begin()
            for col, tipo in novas_cols.items():
                if col not in cols_processo:
                    print(f" > Adicionando coluna '{col}' em processos_disciplina...")
                    try:
                        conn.execute(text(f"ALTER TABLE processos_disciplina ADD COLUMN {col} {tipo}"))
                    except Exception as e:
                        print(f"   [ERRO] {e}")
            conn.commit()

        print("\nProcesso concluído.")

if __name__ == "__main__":
    forcar_fada()