"""dummy for failed migration

Revision ID: a04a281525f8
Revises: ff9f811e0c08
Create Date: 2026-07-30 13:38:39.268079

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a04a281525f8'
down_revision = 'ff9f811e0c08'
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
