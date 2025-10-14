"""Adiciona posto_graduacao ao usuario e nomeia constraint da escola

Revision ID: 365d70a97fe4
Revises: af9e7a05e31e
Create Date: 2025-09-30 12:22:15.884188
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "365d70a97fe4"
down_revision = "af9e7a05e31e"
branch_labels = None
depends_on = None


def _col_exists(bind, table_name: str, column_name: str) -> bool:
    sql = sa.text(
        """
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = :t
          AND COLUMN_NAME = :c
        """
    )
    return bind.execute(sql, {"t": table_name, "c": column_name}).scalar() > 0


def _unique_constraint_exists(bind, table_name: str, constraint_name: str) -> bool:
    sql = sa.text(
        """
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = :t
          AND CONSTRAINT_NAME = :n
          AND CONSTRAINT_TYPE = 'UNIQUE'
        """
    )
    return bind.execute(sql, {"t": table_name, "n": constraint_name}).scalar() > 0


def upgrade():
    bind = op.get_bind()

    # --- 1) Limpa tabela temporária caso exista (idempotente) ---
    op.execute("DROP TABLE IF EXISTS `_alembic_tmp_instrutores`")

    # --- 2) Remove coluna posto_graduacao de instrutores (se existir) ---
    if _col_exists(bind, "instrutores", "posto_graduacao"):
        # batch_alter_table lida bem com MySQL
        with op.batch_alter_table("instrutores", schema=None) as batch_op:
            batch_op.drop_column("posto_graduacao")

    # --- 3) Cria UNIQUE constraint em schools.nome (se não existir) ---
    if not _unique_constraint_exists(bind, "schools", "uq_school_nome"):
        with op.batch_alter_table("schools", schema=None) as batch_op:
            batch_op.create_unique_constraint("uq_school_nome", ["nome"])

    # --- 4) Adiciona coluna posto_graduacao em users (se não existir) ---
    if not _col_exists(bind, "users", "posto_graduacao"):
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(sa.Column("posto_graduacao", sa.String(length=50), nullable=True))


def downgrade():
    bind = op.get_bind()

    # --- 1) Remove coluna posto_graduacao de users (se existir) ---
    if _col_exists(bind, "users", "posto_graduacao"):
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.drop_column("posto_graduacao")

    # --- 2) Remove UNIQUE constraint uq_school_nome (se existir) ---
    if _unique_constraint_exists(bind, "schools", "uq_school_nome"):
        with op.batch_alter_table("schools", schema=None) as batch_op:
            batch_op.drop_constraint("uq_school_nome", type_="unique")

    # --- 3) Recria coluna posto_graduacao em instrutores (se não existir) ---
    if not _col_exists(bind, "instrutores", "posto_graduacao"):
        with op.batch_alter_table("instrutores", schema=None) as batch_op:
            batch_op.add_column(sa.Column("posto_graduacao", sa.VARCHAR(length=50), nullable=True))

    # --- 4) (Compat) Recria a tabela temporária apenas se ainda não existir ---
    # Mantém o comportamento do script original, mas idempotente.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `_alembic_tmp_instrutores` (
          `id` INT NOT NULL,
          `telefone` VARCHAR(15) NULL,
          `is_rr` BOOLEAN NOT NULL,
          `created_at` DATETIME NOT NULL,
          `user_id` INT NOT NULL,
          PRIMARY KEY (`id`),
          UNIQUE KEY `uq__alembic_tmp_instrutores_user_id` (`user_id`),
          CONSTRAINT `fk__alembic_tmp_instrutores_user`
              FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )
