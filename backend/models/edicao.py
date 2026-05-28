# backend/models/edicao.py

from .database import db
from datetime import datetime

class Edicao(db.Model):
    __tablename__ = 'edicoes'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False) # Ex: "CTSP Maio/2026"
    
    # Polo físico que sedia o curso
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    school = db.relationship('School', backref=db.backref('edicoes', lazy='dynamic'))

    # Natureza do curso (determina as regras disciplinares a serem aplicadas)
    npccal_type = db.Column(db.String(20), default='ctsp') # ex: 'ctsp', 'cbfpm', 'cspm'

    # Controle Independente da Avaliação Atitudinal (FADA)
    fada_data_inicio = db.Column(db.DateTime, nullable=True)
    fada_data_fim = db.Column(db.DateTime, nullable=True)

    # A formatura é da Edição (todas as turmas da edição formam-se juntas)
    data_formatura = db.Column(db.Date, nullable=True)

    # Relacionamento inverso com turmas
    turmas = db.relationship('Turma', back_populates='edicao')

    # Relacionamento com alunos e instrutores (isolamento por edição)
    alunos = db.relationship('Aluno', back_populates='edicao', cascade="all, delete-orphan")


    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'school_id': self.school_id,
            'npccal_type': self.npccal_type,
            'fada_data_inicio': self.fada_data_inicio.isoformat() if self.fada_data_inicio else None,
            'fada_data_fim': self.fada_data_fim.isoformat() if self.fada_data_fim else None,
            'data_formatura': self.data_formatura.isoformat() if self.data_formatura else None
        }
