# backend/models/recurso.py

from .database import db
from datetime import datetime, timezone

class DisciplinaHabilitada(db.Model):
    """
    Tabela para registrar quais disciplinas o administrador marcou 
    como tendo provas habilitadas para recursos.
    """
    __tablename__ = 'recurso_disciplinas_habilitadas'
    id = db.Column(db.Integer, primary_key=True)
    disciplina_id = db.Column(db.Integer, db.ForeignKey('disciplinas.id'), unique=True, nullable=False)
    
    # Relacionamento para acessar os dados da disciplina original
    disciplina = db.relationship('Disciplina', backref=db.backref('habilitacao_recurso', uselist=False, cascade='all, delete-orphan'))

class ProvaRecurso(db.Model):
    """
    Tabela para armazenar as Provas criadas pelo Administrador 
    dentro de uma Disciplina para recebimento de Recursos.
    """
    __tablename__ = 'provas_recurso'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    disciplina_id = db.Column(db.Integer, db.ForeignKey('disciplinas.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True)

    # Relacionamentos
    disciplina = db.relationship('Disciplina', backref=db.backref('provas_recurso', lazy=True))
    recursos = db.relationship('Recurso', backref='prova', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ProvaRecurso {self.nome} - Disciplina ID {self.disciplina_id}>'


class Recurso(db.Model):
    """
    Tabela para armazenar os recursos enviados pelos Alunos 
    vinculados a uma Prova e a uma Questão.
    """
    __tablename__ = 'recursos'

    id = db.Column(db.Integer, primary_key=True)
    prova_id = db.Column(db.Integer, db.ForeignKey('provas_recurso.id'), nullable=False)
    aluno_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Dados preenchidos pelo aluno
    questao_texto = db.Column(db.Text, nullable=False)
    argumentacao_texto = db.Column(db.Text, nullable=True)
    arquivo_anexo = db.Column(db.String(255), nullable=True) # Armazena o nome/caminho do PDF ou Word
    
    # Dados de controle da administração
    status = db.Column(db.String(50), default='Pendente') # Valores sugeridos: Pendente, Em Análise, Deferido, Indeferido
    resposta_admin = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relacionamentos (a relação 'prova' já vem do backref de ProvaRecurso)
    aluno = db.relationship('User', backref=db.backref('meus_recursos', lazy=True))

    def __repr__(self):
        return f'<Recurso {self.id} - Prova ID {self.prova_id} - Aluno ID {self.aluno_id}>'