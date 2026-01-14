"""hardening_final_justica_enums_v2

Revision ID: manual_hardening_01
Revises: (COLOCAR O ID ANTERIOR AQUI)
Create Date: 2024-01-20 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# --- ÁREA DE EDIÇÃO MANUAL ---
# 1. Crie um código único qualquer para este arquivo (ex: 'fada123456')
revision = 'hardening_final_v2' 

# 2. COLE AQUI O ID DA MIGRAÇÃO ANTERIOR (que você copiou no Passo 1)
down_revision = '3f58c461810b' 
# -----------------------------

branch_labels = None
depends_on = None

def upgrade():
    # 1. Obtém conexão para inspecionar o banco atual
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # 2. Lista as colunas que JÁ existem na tabela
    columns = [c['name'] for c in inspector.get_columns('processos_disciplina')]
    
    # 3. Usa batch_alter_table para compatibilidade com SQLite
    with op.batch_alter_table('processos_disciplina', schema=None) as batch_op:
        
        # Só adiciona 'regra_id' se ela não existir
        if 'regra_id' not in columns:
            batch_op.add_column(sa.Column('regra_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                'fk_processo_disciplina_regra', 'discipline_rules', ['regra_id'], ['id']
            )
            batch_op.create_index(batch_op.f('ix_processos_disciplina_regra_id'), ['regra_id'], unique=False)

        # Só adiciona 'codigo_infracao' se ela não existir
        if 'codigo_infracao' not in columns:
            batch_op.add_column(sa.Column('codigo_infracao', sa.String(length=50), nullable=True))
            batch_op.create_index('idx_processo_codigo', ['codigo_infracao'], unique=False)

        # Tenta criar o índice de status. 
        try:
            batch_op.create_index('idx_processo_status_data', ['status', 'data_ocorrencia'], unique=False)
        except Exception:
            pass # Índice já deve existir, ignoramos o erro.

def downgrade():
    with op.batch_alter_table('processos_disciplina', schema=None) as batch_op:
        try:
            batch_op.drop_constraint('fk_processo_disciplina_regra', type_='foreignkey')
        except: pass
        
        try: batch_op.drop_index(batch_op.f('ix_processos_disciplina_regra_id'))
        except: pass
        
        try: batch_op.drop_index('idx_processo_codigo')
        except: pass
        
        try: batch_op.drop_index('idx_processo_status_data')
        except: pass
        
        try: batch_op.drop_column('codigo_infracao')
        except: pass
        
        try: batch_op.drop_column('regra_id')
        except: pass