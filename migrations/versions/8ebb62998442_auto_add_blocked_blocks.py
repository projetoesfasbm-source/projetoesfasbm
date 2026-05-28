"""Auto add blocked_blocks

Revision ID: 8ebb62998442
Revises: 043654b10917
Create Date: 2026-05-17 23:51:49.523085

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '8ebb62998442'
down_revision = '043654b10917'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET FOREIGN_KEY_CHECKS = 0;")
    
    try:
        op.drop_table('avaliacao_itens')
    except Exception:
        pass

    try:
        op.drop_table('avaliacoes_atitudinais')
    except Exception:
        pass

    try:
        with op.batch_alter_table('configuracoes_envio', schema=None) as batch_op:
            batch_op.create_unique_constraint('uq_escola_mat_edicao', ['escola_id', 'materia', 'edicao'])
    except Exception:
        pass

    try:
        with op.batch_alter_table('configuracoes_envio', schema=None) as batch_op:
            batch_op.drop_index('uq_escola_materia_envio')
    except Exception:
        pass

    try:
        with op.batch_alter_table('diarios_classe', schema=None) as batch_op:
            batch_op.add_column(sa.Column('is_deleted', sa.Boolean(), server_default='0', nullable=False))
    except Exception:
        pass

    try:
        with op.batch_alter_table('diarios_classe', schema=None) as batch_op:
            batch_op.alter_column('status',
                   existing_type=mysql.VARCHAR(length=50),
                   type_=sa.String(length=20),
                   nullable=False,
                   existing_server_default=sa.text("'pendente'"))
    except Exception:
        pass

    try:
        with op.batch_alter_table('diarios_classe', schema=None) as batch_op:
            batch_op.alter_column('updated_at',
                   existing_type=mysql.DATETIME(),
                   nullable=False,
                   existing_server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    except Exception:
        pass

    try:
        with op.batch_alter_table('diarios_classe', schema=None) as batch_op:
            batch_op.create_foreign_key(None, 'users', ['instrutor_assinante_id'], ['id'])
    except Exception:
        pass

    try:
        with op.batch_alter_table('elogios', schema=None) as batch_op:
            batch_op.alter_column('data_registro',
                   existing_type=mysql.DATETIME(),
                   nullable=False,
                   existing_server_default=sa.text('CURRENT_TIMESTAMP'))
    except Exception:
        pass

    try:
        with op.batch_alter_table('elogios', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_elogios_aluno_id'), ['aluno_id'], unique=False)
    except Exception:
        pass

    try:
        with op.batch_alter_table('fada_avaliacoes', schema=None) as batch_op:
            batch_op.alter_column('lancador_id',
                   existing_type=mysql.INTEGER(),
                   nullable=False)
            batch_op.alter_column('data_avaliacao',
                   existing_type=mysql.DATETIME(),
                   nullable=False)
            for attr in ['expressao', 'planejamento', 'perseveranca', 'apresentacao', 'lealdade', 'tato', 'equilibrio', 'disciplina', 'responsabilidade', 'maturidade', 'assiduidade', 'pontualidade', 'diccao', 'lideranca', 'relacionamento', 'etica', 'produtividade', 'eficiencia', 'media_final', 'ndisc_snapshot', 'aat_snapshot']:
                try:
                    batch_op.alter_column(attr, existing_type=mysql.FLOAT(), nullable=False, existing_server_default=sa.text("'0'"))
                except Exception:
                    pass
            batch_op.alter_column('status',
                   existing_type=mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=20),
                   nullable=False,
                   existing_server_default=sa.text("'RASCUNHO'"))
    except Exception:
        pass

    try:
        with op.batch_alter_table('fada_avaliacoes', schema=None) as batch_op:
            batch_op.drop_constraint('fada_avaliacoes_ibfk_2', type_='foreignkey')
    except Exception:
        pass

    try:
        with op.batch_alter_table('fada_avaliacoes', schema=None) as batch_op:
            batch_op.create_foreign_key(None, 'users', ['presidente_id'], ['id'])
            batch_op.create_foreign_key(None, 'users', ['membro1_id'], ['id'])
            batch_op.create_foreign_key(None, 'users', ['membro2_id'], ['id'])
            batch_op.create_foreign_key(None, 'users', ['lancador_id'], ['id'])
    except Exception:
        pass

    try:
        with op.batch_alter_table('fada_avaliacoes', schema=None) as batch_op:
            batch_op.drop_column('avaliador_id')
    except Exception:
        pass

    try:
        with op.batch_alter_table('processos_disciplina', schema=None) as batch_op:
            batch_op.alter_column('data_registro',
                   existing_type=mysql.DATETIME(),
                   nullable=False)
            batch_op.alter_column('is_crime',
                   existing_type=mysql.TINYINT(display_width=1),
                   nullable=False,
                   existing_server_default=sa.text("'0'"))
            batch_op.alter_column('tipo_sancao',
                   existing_type=mysql.VARCHAR(length=100),
                   type_=sa.String(length=50),
                   existing_nullable=True)
            batch_op.alter_column('dias_sancao',
                   existing_type=mysql.INTEGER(),
                   nullable=False,
                   existing_server_default=sa.text("'0'"))
            batch_op.alter_column('origem_punicao',
                   existing_type=mysql.VARCHAR(length=100),
                   type_=sa.String(length=20),
                   nullable=False)
            batch_op.alter_column('ciente_aluno',
                   existing_type=mysql.TINYINT(display_width=1),
                   nullable=False,
                   existing_server_default=sa.text("'0'"))
    except Exception:
        pass

    for idx in ['idx_processo_codigo', 'idx_processo_status_data', 'ix_processos_disciplina_aluno_id', 'ix_processos_disciplina_regra_id', 'ix_processos_disciplina_relator_id']:
        try:
            with op.batch_alter_table('processos_disciplina', schema=None) as batch_op:
                batch_op.drop_index(idx)
        except Exception:
            pass

    try:
        with op.batch_alter_table('processos_disciplina', schema=None) as batch_op:
            batch_op.create_foreign_key(None, 'users', ['autoridade_recurso_id'], ['id'])
    except Exception:
        pass

    try:
        with op.batch_alter_table('semanas', schema=None) as batch_op:
            batch_op.add_column(sa.Column('blocked_blocks', sa.Text(), nullable=True))
    except Exception:
        pass

    try:
        with op.batch_alter_table('semanas', schema=None) as batch_op:
            batch_op.alter_column('priority_active',
                   existing_type=mysql.TINYINT(display_width=1),
                   nullable=False,
                   existing_server_default=sa.text("'0'"))
    except Exception:
        pass

    try:
        with op.batch_alter_table('semanas', schema=None) as batch_op:
            batch_op.drop_column('prioridade_disciplinas')
    except Exception:
        pass

    try:
        with op.batch_alter_table('semanas', schema=None) as batch_op:
            batch_op.drop_column('prioridade_status')
    except Exception:
        pass

    try:
        with op.batch_alter_table('turmas', schema=None) as batch_op:
            batch_op.alter_column('ano',
                   existing_type=mysql.INTEGER(),
                   type_=sa.String(length=20),
                   nullable=False)
    except Exception:
        pass

    try:
        with op.batch_alter_table('turmas', schema=None) as batch_op:
            batch_op.drop_index('nome')
    except Exception:
        pass

    try:
        with op.batch_alter_table('turmas', schema=None) as batch_op:
            batch_op.create_unique_constraint('uq_turma_nome_escola', ['nome', 'school_id'])
    except Exception:
        pass

    try:
        with op.batch_alter_table('user_schools', schema=None) as batch_op:
            batch_op.alter_column('role',
                   existing_type=mysql.VARCHAR(length=20),
                   type_=sa.String(length=50),
                   existing_nullable=False)
    except Exception:
        pass

    op.execute("SET FOREIGN_KEY_CHECKS = 1;")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user_schools', schema=None) as batch_op:
        batch_op.alter_column('role',
               existing_type=sa.String(length=50),
               type_=mysql.VARCHAR(length=20),
               existing_nullable=False)

    with op.batch_alter_table('turmas', schema=None) as batch_op:
        batch_op.drop_constraint('uq_turma_nome_escola', type_='unique')
        batch_op.create_index(batch_op.f('nome'), ['nome'], unique=True)
        batch_op.alter_column('ano',
               existing_type=sa.String(length=20),
               type_=mysql.INTEGER(),
               nullable=True)

    with op.batch_alter_table('semanas', schema=None) as batch_op:
        batch_op.add_column(sa.Column('prioridade_status', mysql.TINYINT(display_width=1), server_default=sa.text("'0'"), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('prioridade_disciplinas', mysql.TEXT(), nullable=True))
        batch_op.alter_column('priority_active',
               existing_type=mysql.TINYINT(display_width=1),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.drop_column('blocked_blocks')

    with op.batch_alter_table('processos_disciplina', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_index(batch_op.f('ix_processos_disciplina_relator_id'), ['relator_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_processos_disciplina_regra_id'), ['regra_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_processos_disciplina_aluno_id'), ['aluno_id'], unique=False)
        batch_op.create_index(batch_op.f('idx_processo_status_data'), ['status', 'data_ocorrencia'], unique=False)
        batch_op.create_index(batch_op.f('idx_processo_codigo'), ['codigo_infracao'], unique=False)
        batch_op.alter_column('ciente_aluno',
               existing_type=mysql.TINYINT(display_width=1),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('origem_punicao',
               existing_type=sa.String(length=20),
               type_=mysql.VARCHAR(length=100),
               nullable=True)
        batch_op.alter_column('dias_sancao',
               existing_type=mysql.INTEGER(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('tipo_sancao',
               existing_type=sa.String(length=50),
               type_=mysql.VARCHAR(length=100),
               existing_nullable=True)
        batch_op.alter_column('is_crime',
               existing_type=mysql.TINYINT(display_width=1),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('data_registro',
               existing_type=mysql.DATETIME(),
               nullable=True)

    with op.batch_alter_table('fada_avaliacoes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('avaliador_id', mysql.INTEGER(), autoincrement=False, nullable=False))
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key(batch_op.f('fada_avaliacoes_ibfk_2'), 'users', ['avaliador_id'], ['id'])
        batch_op.alter_column('aat_snapshot',
               existing_type=mysql.FLOAT(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('ndisc_snapshot',
               existing_type=mysql.FLOAT(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('status',
               existing_type=mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=20),
               nullable=True,
               existing_server_default=sa.text("'RASCUNHO'"))
        batch_op.alter_column('media_final',
               existing_type=mysql.FLOAT(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('eficiencia',
               existing_type=mysql.FLOAT(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('produtividade',
               existing_type=mysql.FLOAT(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('etica',
               existing_type=mysql.FLOAT(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('relacionamento',
               existing_type=mysql.FLOAT(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('lideranca',
               existing_type=mysql.FLOAT(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('diccao',
               existing_type=mysql.FLOAT(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('pontualidade',
               existing_type=mysql.FLOAT(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('assiduidade',
               existing_type=mysql.FLOAT(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('maturidade',
               existing_type=mysql.FLOAT(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('responsabilidade',
               existing_type=mysql.FLOAT(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('disciplina',
               existing_type=mysql.FLOAT(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('equilibrio',
               existing_type=mysql.FLOAT(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('tato',
               existing_type=mysql.FLOAT(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('lealdade',
               existing_type=mysql.FLOAT(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('apresentacao',
               existing_type=mysql.FLOAT(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('perseveranca',
               existing_type=mysql.FLOAT(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('planejamento',
               existing_type=mysql.FLOAT(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('expressao',
               existing_type=mysql.FLOAT(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('data_avaliacao',
               existing_type=mysql.DATETIME(),
               nullable=True)
        batch_op.alter_column('lancador_id',
               existing_type=mysql.INTEGER(),
               nullable=True)

    with op.batch_alter_table('elogios', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_elogios_aluno_id'))
        batch_op.alter_column('data_registro',
               existing_type=mysql.DATETIME(),
               nullable=True,
               existing_server_default=sa.text('CURRENT_TIMESTAMP'))

    with op.batch_alter_table('diarios_classe', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.alter_column('updated_at',
               existing_type=mysql.DATETIME(),
               nullable=True,
               existing_server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
        batch_op.alter_column('status',
               existing_type=sa.String(length=20),
               type_=mysql.VARCHAR(length=50),
               nullable=True,
               existing_server_default=sa.text("'pendente'"))
        batch_op.drop_column('is_deleted')

    with op.batch_alter_table('configuracoes_envio', schema=None) as batch_op:
        batch_op.drop_constraint('uq_escola_mat_edicao', type_='unique')
        batch_op.create_index(batch_op.f('uq_escola_materia_envio'), ['escola_id', 'materia'], unique=True)

    op.create_table('avaliacao_itens',
    sa.Column('id', mysql.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('avaliacao_id', mysql.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('criterio', mysql.VARCHAR(length=100), nullable=False),
    sa.Column('nota', mysql.FLOAT(), nullable=False),
    sa.ForeignKeyConstraint(['avaliacao_id'], ['avaliacoes_atitudinais.id'], name=op.f('avaliacao_itens_ibfk_1')),
    sa.PrimaryKeyConstraint('id'),
    mysql_default_charset='utf8mb3',
    mysql_engine='InnoDB'
    )
    with op.batch_alter_table('avaliacao_itens', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_avaliacao_itens_avaliacao_id'), ['avaliacao_id'], unique=False)

    op.create_table('avaliacoes_atitudinais',
    sa.Column('id', mysql.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('aluno_id', mysql.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('avaliador_id', mysql.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('created_at', mysql.DATETIME(), server_default=sa.text('(now())'), nullable=False),
    sa.Column('data_fechamento', mysql.DATETIME(), nullable=True),
    sa.Column('periodo_inicio', mysql.DATETIME(), nullable=False),
    sa.Column('periodo_fim', mysql.DATETIME(), nullable=False),
    sa.Column('status', mysql.VARCHAR(length=20), nullable=False),
    sa.Column('nota_disciplinar', mysql.FLOAT(), nullable=False),
    sa.Column('nota_fada', mysql.FLOAT(), nullable=False),
    sa.Column('nota_final', mysql.FLOAT(), nullable=False),
    sa.Column('observacoes', mysql.TEXT(), nullable=True),
    sa.Column('updated_at', mysql.DATETIME(), server_default=sa.text('(now())'), nullable=False),
    sa.ForeignKeyConstraint(['aluno_id'], ['alunos.id'], name=op.f('avaliacoes_atitudinais_ibfk_1')),
    sa.ForeignKeyConstraint(['avaliador_id'], ['users.id'], name=op.f('avaliacoes_atitudinais_ibfk_2')),
    sa.PrimaryKeyConstraint('id'),
    mysql_default_charset='utf8mb3',
    mysql_engine='InnoDB'
    )
    with op.batch_alter_table('avaliacoes_atitudinais', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_avaliacoes_atitudinais_avaliador_id'), ['avaliador_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_avaliacoes_atitudinais_aluno_id'), ['aluno_id'], unique=False)

    # ### end Alembic commands ###
