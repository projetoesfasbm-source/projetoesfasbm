"""Add priority_blocks column to semanas table."""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260120_add_priority_blocks_to_semanas"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Adiciona a coluna apenas se ainda não existir
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    columns = [c["name"] for c in inspector.get_columns("semanas")]

    if "priority_blocks" not in columns:
        op.add_column(
            "semanas",
            sa.Column("priority_blocks", sa.Text(), nullable=True),
        )


def downgrade():
    op.drop_column("semanas", "priority_blocks")
