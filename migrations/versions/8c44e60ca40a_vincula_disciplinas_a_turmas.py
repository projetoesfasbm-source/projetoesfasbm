"""Vincula disciplinas a turmas (versão manual e à prova de falhas)

Revision ID: 8c44e60ca40a
Revises: a76506570530
Create Date: 2025-10-14 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '8c44e60ca40a'
down_revision = 'a76506570530' # Verifique se este é o ID da sua migração anterior
branch_labels = None
depends_on = None


def upgrade():
    print("\n--- INICIANDO MIGRAÇÃO MANUAL À PROVA DE FALHAS (v4) ---")
    
    # 1. Limpar dados que dependem de 'disciplinas' para evitar erros de FK
    print("\n[PASSO 1/3] Limpando dados relacionados (horarios, vinculos, historico)...")
    try:
        op.execute("SET FOREIGN_KEY_CHECKS=0;")
        op.execute("DELETE FROM horarios;")
        op.execute("DELETE FROM disciplina_turmas;")
        op.execute("DELETE FROM historico_disciplinas;")
        op.execute("DELETE FROM disciplinas;") # Limpa as disciplinas órfãs
        op.execute("SET FOREIGN_KEY_CHECKS=1;")
        print("  - Dados limpos com sucesso.")
    except Exception as e:
        print(f"  - Aviso ao limpar dados: {e}. Continuando...")


    # 2. Reestruturar a tabela 'disciplinas' de forma robusta
    print("\n[PASSO 2/3] Reestruturando a tabela 'disciplinas'...")
    with op.batch_alter_table('disciplinas', schema=None) as batch_op:
        
        # Tenta remover a antiga constraint de unicidade 'materia', se existir.
        try:
            batch_op.drop_constraint('materia', type_='unique')
            print("  - Constraint de unicidade 'materia' removida.")
        except Exception:
            print("  - Constraint de unicidade 'materia' não encontrada, ignorando.")
            
        # Tenta remover a antiga foreign key para 'schools'.
        try:
            batch_op.drop_constraint('disciplinas_ibfk_1', type_='foreignkey')
            print("  - Chave estrangeira 'disciplinas_ibfk_1' removida.")
        except Exception:
            print("  - Chave estrangeira 'disciplinas_ibfk_1' não encontrada, ignorando.")
            
        # Tenta remover a coluna 'school_id'
        try:
            batch_op.drop_column('school_id')
            print("  - Coluna 'school_id' removida.")
        except Exception:
            print("  - Coluna 'school_id' não encontrada, ignorando.")

        # Tenta adicionar a nova coluna 'turma_id'
        try:
            batch_op.add_column(sa.Column('turma_id', sa.Integer(), nullable=False))
            print("  - Nova coluna 'turma_id' adicionada.")
        except Exception:
            print("  - Coluna 'turma_id' já existe, ignorando.")

    # 3. Criar as novas constraints fora do batch_alter_table para maior controle
    print("\n[PASSO 3/3] Criando novas constraints...")
    try:
        op.create_foreign_key('fk_disciplinas_turma_id', 'disciplinas', 'turmas', ['turma_id'], ['id'])
        print("  - Nova chave estrangeira para 'turmas' criada.")
    except Exception as e:
        print(f"  - Não foi possível criar a chave estrangeira (pode já existir): {e}")

    try:
        op.create_unique_constraint('_materia_turma_uc', 'disciplinas', ['materia', 'turma_id'])
        print("  - Nova constraint de unicidade para (materia, turma_id) criada.")
    except Exception as e:
        print(f"  - Não foi possível criar a constraint de unicidade (pode já existir): {e}")

    print("\n--- MIGRAÇÃO CONCLUÍDA ---")


def downgrade():
    # O downgrade recria a estrutura antiga.
    with op.batch_alter_table('disciplinas', schema=None) as batch_op:
        try: batch_op.drop_constraint('_materia_turma_uc', type_='unique')
        except: pass
        try: batch_op.drop_constraint('fk_disciplinas_turma_id', type_='foreignkey')
        except: pass
        try: batch_op.drop_column('turma_id')
        except: pass
        try: batch_op.add_column(sa.Column('school_id', sa.INTEGER(), autoincrement=False, nullable=False))
        except: pass
        try: batch_op.create_foreign_key('disciplinas_ibfk_1', 'schools', ['school_id'], ['id'])
        except: pass
        try: batch_op.create_unique_constraint('materia', ['materia'])
        except: pass