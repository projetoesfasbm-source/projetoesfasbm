"""Adiciona foto_perfil ao instrutor

Revision ID: c5c6e8b5d3a2
Revises: e1b711a38a7c
Create Date: 2025-10-15 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c5c6e8b5d3a2'
down_revision = 'e1b711a38a7c'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('instrutores', schema=None) as batch_op:
        batch_op.add_column(sa.Column('foto_perfil', sa.String(length=255), nullable=True, server_default='default.png'))

def downgrade():
    with op.batch_alter_table('instrutores', schema=None) as batch_op:
        batch_op.drop_column('foto_perfil')