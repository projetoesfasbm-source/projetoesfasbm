"""Removendo coluna redundante etapa_atual de FadaAvaliacao

Revision ID: 54f30bd67373
Revises: c989669e555f
Create Date: 2026-05-09 01:33:45.682965

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '54f30bd67373'
down_revision = 'c989669e555f'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('fada_avaliacoes')]
    if 'etapa_atual' in columns:
        op.drop_column('fada_avaliacoes', 'etapa_atual')


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('fada_avaliacoes')]
    if 'etapa_atual' not in columns:
        op.add_column('fada_avaliacoes', sa.Column('etapa_atual', sa.String(length=50), nullable=True))
