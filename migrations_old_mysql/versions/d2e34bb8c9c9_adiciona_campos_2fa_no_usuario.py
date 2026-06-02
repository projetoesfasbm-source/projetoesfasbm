"""Adiciona campos 2FA no usuario

Revision ID: d2e34bb8c9c9
Revises: bfa033980237
Create Date: 2026-04-14 13:43:34.974091

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd2e34bb8c9c9'
down_revision = 'bfa033980237'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('users')]
    
    # Adiciona coluna totp_secret na tabela users
    if 'totp_secret' not in columns:
        op.add_column('users', sa.Column('totp_secret', sa.String(32), nullable=True))
    
    # Adiciona coluna is_totp_enabled na tabela users
    if 'is_totp_enabled' not in columns:
        op.add_column('users', sa.Column('is_totp_enabled', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    # Remove as colunas em caso de rollback
    op.drop_column('users', 'is_totp_enabled')
    op.drop_column('users', 'totp_secret')