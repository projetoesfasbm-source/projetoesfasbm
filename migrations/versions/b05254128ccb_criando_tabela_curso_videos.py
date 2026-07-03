"""Criando tabela curso_videos

Revision ID: b05254128ccb
Revises: 6dd1cde59b0d
Create Date: 2026-07-01 08:47:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b05254128ccb'
down_revision: Union[str, None] = '6dd1cde59b0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('curso_videos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('thumbnail', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('curso_videos')
