"""Add group_id to Horario model

Revision ID: 2b5b88901a2f
Revises: a698f13f0f69
Create Date: 2025-10-17 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2b5b88901a2f'
down_revision = 'a698f13f0f69' # O ID da sua última migração
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('horarios', schema=None) as batch_op:
        batch_op.add_column(sa.Column('group_id', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_horarios_group_id'), ['group_id'], unique=False)


def downgrade():
    with op.batch_alter_table('horarios', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_horarios_group_id'))
        batch_op.drop_column('group_id')