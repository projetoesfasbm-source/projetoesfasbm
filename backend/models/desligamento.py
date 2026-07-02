from .database import db
from datetime import datetime

class RegistroDesligamento(db.Model):
    __tablename__ = 'registro_desligamentos'
    
    id = db.Column(db.Integer, primary_key=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey('alunos.id'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False) # Quem executou o desligamento
    edicao_id = db.Column(db.Integer, db.ForeignKey('edicoes.id'), nullable=False)
    
    data_desligamento = db.Column(db.DateTime, default=datetime.utcnow)
    motivo = db.Column(db.String(100), nullable=False) # Ex: 'Limite de Faltas', 'Disciplinar', 'Desistência', 'Outros'
    observacoes = db.Column(db.Text, nullable=True) # Detalhes ou número do Boletim
    
    # Relacionamentos
    aluno = db.relationship('Aluno', backref=db.backref('historico_desligamentos', lazy=True))
    admin = db.relationship('User', foreign_keys=[admin_id])
    edicao = db.relationship('Edicao', foreign_keys=[edicao_id])
