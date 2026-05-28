from .database import db
from datetime import datetime

class BackgroundJob(db.Model):
    __tablename__ = 'background_jobs'

    id = db.Column(db.String(36), primary_key=True) # UUID
    task_type = db.Column(db.String(50), nullable=False) # ex: 'generate_pdf'
    status = db.Column(db.String(20), nullable=False, default='pending') # pending, processing, completed, failed
    
    # Payload can be large HTML string for PDF generation, so use Text or MediumText
    payload = db.Column(db.Text(16777215), nullable=True) # MediumText in MySQL
    
    # Store other metadata as JSON if needed (like school_id, orientacao)
    meta_data = db.Column(db.Text, nullable=True) 
    
    result_path = db.Column(db.String(255), nullable=True) # Caminho onde o PDF foi salvo
    error_message = db.Column(db.Text, nullable=True)
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    user = db.relationship('User', backref=db.backref('background_jobs', lazy='dynamic'))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'task_type': self.task_type,
            'status': self.status,
            'result_path': self.result_path,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'finished_at': self.finished_at.isoformat() if self.finished_at else None
        }
