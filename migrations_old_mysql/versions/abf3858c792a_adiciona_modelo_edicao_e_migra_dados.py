"""Adiciona modelo Edicao e migra dados

Revision ID: abf3858c792a
Revises: 8ebb62998442
Create Date: 2026-05-26 14:56:55.539585

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'abf3858c792a'
down_revision = '8ebb62998442'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.create_table('edicoes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=100), nullable=False),
        sa.Column('school_id', sa.Integer(), nullable=False),
        sa.Column('npccal_type', sa.String(length=20), nullable=True),
        sa.Column('fada_data_inicio', sa.DateTime(), nullable=True),
        sa.Column('fada_data_fim', sa.DateTime(), nullable=True),
        sa.Column('data_formatura', sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    except Exception:
        pass
    
    try:
        with op.batch_alter_table('turmas', schema=None) as batch_op:
            batch_op.add_column(sa.Column('edicao_id', sa.Integer(), nullable=True))
    except Exception:
        pass

    try:
        with op.batch_alter_table('turmas', schema=None) as batch_op:
            batch_op.alter_column('ano',
                   existing_type=mysql.INTEGER(),
                   type_=sa.String(length=20),
                   nullable=False)
    except Exception:
        pass

    try:
        with op.batch_alter_table('turmas', schema=None) as batch_op:
            batch_op.drop_index('nome')
    except Exception:
        pass

    try:
        with op.batch_alter_table('turmas', schema=None) as batch_op:
            batch_op.create_unique_constraint('uq_turma_nome_escola', ['nome', 'school_id'])
    except Exception:
        pass

    try:
        with op.batch_alter_table('turmas', schema=None) as batch_op:
            batch_op.create_foreign_key(None, 'edicoes', ['edicao_id'], ['id'])
    except Exception:
        pass

    # --- DATA MIGRATION ---
    connection = op.get_bind()
    try:
        connection.execute(sa.text("""
            INSERT INTO edicoes (nome, school_id, npccal_type, data_formatura)
            SELECT 'Edição Padrão', s.id, s.npccal_type, 
                   (SELECT MAX(t.data_formatura) FROM turmas t WHERE t.school_id = s.id)
            FROM schools s
        """))
    except Exception:
        pass
    try:
        connection.execute(sa.text("""
            UPDATE turmas t
            JOIN edicoes e ON t.school_id = e.school_id
            SET t.edicao_id = e.id
        """))
    except Exception:
        pass
    # ----------------------

    try:
        with op.batch_alter_table('schools', schema=None) as batch_op:
            batch_op.drop_column('npccal_type')
    except Exception:
        pass

    try:
        with op.batch_alter_table('turmas', schema=None) as batch_op:
            batch_op.drop_column('data_formatura')
    except Exception:
        pass


def downgrade():
    with op.batch_alter_table('turmas', schema=None) as batch_op:
        batch_op.add_column(sa.Column('data_formatura', sa.DATE(), nullable=True))
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint('uq_turma_nome_escola', type_='unique')
        batch_op.create_index(batch_op.f('nome'), ['nome'], unique=True)
        batch_op.alter_column('ano',
               existing_type=sa.String(length=20),
               type_=mysql.INTEGER(),
               nullable=True)
        batch_op.drop_column('edicao_id')

    with op.batch_alter_table('schools', schema=None) as batch_op:
        batch_op.add_column(sa.Column('npccal_type', mysql.VARCHAR(length=20), server_default=sa.text("'cfs'"), nullable=False))

    op.drop_table('edicoes')
