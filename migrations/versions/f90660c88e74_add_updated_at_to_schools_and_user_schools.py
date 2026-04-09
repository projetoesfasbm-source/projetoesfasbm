from alembic import op
import sqlalchemy as sa

# Preencha automaticamente: o Flask-Migrate já coloca os valores corretos
revision = "f90660c88e74"
down_revision = "ca52924392cd"
branch_labels = None
depends_on = None


def upgrade():
    # 1) schools.updated_at (cria como NULL primeiro)
    with op.batch_alter_table("schools") as batch:
        batch.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))

    # Preenche updated_at existente com created_at (ou NOW() se preferir)
    op.execute("UPDATE schools SET updated_at = COALESCE(updated_at, created_at)")

    # Ajusta para NOT NULL + default + ON UPDATE (MySQL)
    op.execute(
        """
        ALTER TABLE schools
        MODIFY COLUMN updated_at DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP
        """
    )

    # 2) user_schools.updated_at (mesma sequência)
    with op.batch_alter_table("user_schools") as batch:
        batch.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))

    op.execute(
        "UPDATE user_schools SET updated_at = COALESCE(updated_at, created_at)"
    )

    op.execute(
        """
        ALTER TABLE user_schools
        MODIFY COLUMN updated_at DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP
        """
    )


def downgrade():
    with op.batch_alter_table("user_schools") as batch:
        batch.drop_column("updated_at")

    with op.batch_alter_table("schools") as batch:
        batch.drop_column("updated_at")

