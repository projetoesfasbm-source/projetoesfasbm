"""Migrate questoes to edicao_id

Revision ID: aff76803dd78
Revises: 704e81d438e0
Create Date: 2026-05-27 22:44:22.679140

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'aff76803dd78'
down_revision = '704e81d438e0'
branch_labels = None
depends_on = None


def column_exists(conn, table, column):
    result = conn.execute(text(
        f"SELECT COUNT(*) FROM information_schema.columns "
        f"WHERE table_schema = DATABASE() AND table_name = '{table}' AND column_name = '{column}'"
    ))
    return result.scalar() > 0

def index_exists(conn, table, index):
    result = conn.execute(text(
        f"SELECT COUNT(*) FROM information_schema.statistics "
        f"WHERE table_schema = DATABASE() AND table_name = '{table}' AND index_name = '{index}'"
    ))
    return result.scalar() > 0

def fk_exists(conn, table, constraint):
    result = conn.execute(text(
        f"SELECT COUNT(*) FROM information_schema.table_constraints "
        f"WHERE table_schema = DATABASE() AND table_name = '{table}' "
        f"AND constraint_name = '{constraint}' AND constraint_type = 'FOREIGN KEY'"
    ))
    return result.scalar() > 0


def upgrade():
    conn = op.get_bind()

    # --- configuracoes_envio ---
    if not column_exists(conn, 'configuracoes_envio', 'edicao_id'):
        conn.execute(text("ALTER TABLE configuracoes_envio ADD COLUMN edicao_id INTEGER"))

    if not fk_exists(conn, 'configuracoes_envio', 'fk_conf_envio_edicao_id'):
        conn.execute(text(
            "ALTER TABLE configuracoes_envio "
            "ADD CONSTRAINT fk_conf_envio_edicao_id FOREIGN KEY (edicao_id) REFERENCES edicoes(id)"
        ))

    if not index_exists(conn, 'configuracoes_envio', 'uq_escola_mat_edicao_id'):
        conn.execute(text(
            "ALTER TABLE configuracoes_envio "
            "ADD CONSTRAINT uq_escola_mat_edicao_id UNIQUE (escola_id, materia, edicao_id)"
        ))

    # Dropar index antigo: precisa remover FK que o usa antes
    if index_exists(conn, 'configuracoes_envio', 'uq_escola_mat_edicao'):
        # Encontra e dropa FKs que referenciam esse índice
        fks = conn.execute(text(
            "SELECT constraint_name FROM information_schema.table_constraints "
            "WHERE table_schema = DATABASE() AND table_name = 'configuracoes_envio' "
            "AND constraint_type = 'FOREIGN KEY'"
        )).fetchall()
        for fk in fks:
            conn.execute(text(f"ALTER TABLE configuracoes_envio DROP FOREIGN KEY `{fk[0]}`"))
        conn.execute(text("ALTER TABLE configuracoes_envio DROP INDEX uq_escola_mat_edicao"))

    if column_exists(conn, 'configuracoes_envio', 'edicao'):
        conn.execute(text("ALTER TABLE configuracoes_envio DROP COLUMN edicao"))

    # --- delegacoes_prova ---
    if not column_exists(conn, 'delegacoes_prova', 'edicao_id'):
        conn.execute(text("ALTER TABLE delegacoes_prova ADD COLUMN edicao_id INTEGER"))

    if not fk_exists(conn, 'delegacoes_prova', 'fk_delegacao_edicao_id'):
        conn.execute(text(
            "ALTER TABLE delegacoes_prova "
            "ADD CONSTRAINT fk_delegacao_edicao_id FOREIGN KEY (edicao_id) REFERENCES edicoes(id)"
        ))

    if column_exists(conn, 'delegacoes_prova', 'edicao'):
        conn.execute(text("ALTER TABLE delegacoes_prova DROP COLUMN edicao"))

    # --- questoes_banco ---
    if not column_exists(conn, 'questoes_banco', 'edicao_id'):
        conn.execute(text("ALTER TABLE questoes_banco ADD COLUMN edicao_id INTEGER"))

    if not fk_exists(conn, 'questoes_banco', 'fk_questao_edicao_id'):
        conn.execute(text(
            "ALTER TABLE questoes_banco "
            "ADD CONSTRAINT fk_questao_edicao_id FOREIGN KEY (edicao_id) REFERENCES edicoes(id)"
        ))

    if column_exists(conn, 'questoes_banco', 'edicao'):
        conn.execute(text("ALTER TABLE questoes_banco DROP COLUMN edicao"))

    # --- background_jobs - corrigir tipo da coluna payload ---
    conn.execute(text(
        "ALTER TABLE background_jobs MODIFY COLUMN payload MEDIUMTEXT"
    ))


def downgrade():
    conn = op.get_bind()

    conn.execute(text("ALTER TABLE questoes_banco DROP FOREIGN KEY fk_questao_edicao_id"))
    conn.execute(text("ALTER TABLE questoes_banco DROP COLUMN edicao_id"))
    conn.execute(text("ALTER TABLE questoes_banco ADD COLUMN edicao VARCHAR(100) NOT NULL DEFAULT 'Geral'"))

    conn.execute(text("ALTER TABLE delegacoes_prova DROP FOREIGN KEY fk_delegacao_edicao_id"))
    conn.execute(text("ALTER TABLE delegacoes_prova DROP COLUMN edicao_id"))
    conn.execute(text("ALTER TABLE delegacoes_prova ADD COLUMN edicao VARCHAR(100) NOT NULL DEFAULT 'Geral'"))

    conn.execute(text("ALTER TABLE configuracoes_envio DROP FOREIGN KEY fk_conf_envio_edicao_id"))
    conn.execute(text("ALTER TABLE configuracoes_envio DROP INDEX uq_escola_mat_edicao_id"))
    conn.execute(text("ALTER TABLE configuracoes_envio DROP COLUMN edicao_id"))
    conn.execute(text("ALTER TABLE configuracoes_envio ADD COLUMN edicao VARCHAR(100) NOT NULL DEFAULT 'Geral'"))
    conn.execute(text("ALTER TABLE configuracoes_envio ADD UNIQUE KEY uq_escola_mat_edicao (escola_id, materia, edicao)"))
