# backend/models/banco_questoes.py

from .database import db
from datetime import datetime

class QuestaoBanco(db.Model):
    __tablename__ = 'questoes_banco'

    id = db.Column(db.Integer, primary_key=True)
    disciplina_id = db.Column(db.Integer, db.ForeignKey('disciplinas.id'), nullable=False)
    escola_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    instrutor_id = db.Column(db.Integer, db.ForeignKey('instrutores.id'), nullable=False)
    edicao = db.Column(db.String(100), nullable=False, default="Geral", server_default="Geral")

    assunto = db.Column(db.String(255), nullable=True)
    enunciado = db.Column(db.Text, nullable=False)
    alternativas = db.Column(db.JSON, nullable=False)  # Armazena {"A": "...", "B": "..."}
    resposta_correta = db.Column(db.String(1), nullable=False)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    ativo = db.Column(db.Boolean, default=True)

    # Relacionamentos com Cascade para garantir que se a disciplina/escola/instrutor sumir, as questões somem
    disciplina = db.relationship('Disciplina', backref=db.backref('questoes_banco', cascade='all, delete-orphan'))
    escola = db.relationship('School', backref=db.backref('questoes_banco', cascade='all, delete-orphan'))
    instrutor = db.relationship('Instrutor', backref=db.backref('questoes_enviadas', cascade='all, delete-orphan'))

class ConfiguracaoEnvio(db.Model):
    """Tabela que salva se o envio está aberto ou fechado"""
    __tablename__ = 'configuracoes_envio'

    id = db.Column(db.Integer, primary_key=True)
    escola_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    materia = db.Column(db.String(100), nullable=False)
    envio_ativo = db.Column(db.Boolean, default=False)
    edicao = db.Column(db.String(100), nullable=False, default="Geral", server_default="Geral")

    __table_args__ = (db.UniqueConstraint('escola_id', 'materia', 'edicao', name='uq_escola_mat_edicao'),)

class DelegacaoProva(db.Model):
    __tablename__ = 'delegacoes_prova'

    id = db.Column(db.Integer, primary_key=True)
    instrutor_id = db.Column(db.Integer, db.ForeignKey('instrutores.id'), nullable=False)
    escola_gestora_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    disciplina_id = db.Column(db.Integer, db.ForeignKey('disciplinas.id'), nullable=False)
    edicao = db.Column(db.String(100), nullable=False, default="Geral", server_default="Geral")

    escolas_fontes = db.Column(db.JSON, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos com Cascade
    instrutor = db.relationship('Instrutor', backref=db.backref('delegacoes_recebidas', cascade='all, delete-orphan'))
    escola_gestora = db.relationship('School', backref=db.backref('provas_geridas', cascade='all, delete-orphan'))
    disciplina = db.relationship('Disciplina', backref=db.backref('delegacoes_prova', cascade='all, delete-orphan'))

class RascunhoProva(db.Model):
    __tablename__ = 'rascunhos_prova'

    id = db.Column(db.Integer, primary_key=True)
    delegacao_id = db.Column(db.Integer, db.ForeignKey('delegacoes_prova.id'), nullable=False)
    questoes_selecionadas = db.Column(db.JSON, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamentos com Cascade (se a delegacao sumir, o rascunho some)
    delegacao = db.relationship('DelegacaoProva', backref=db.backref('rascunho', uselist=False, cascade='all, delete-orphan'))