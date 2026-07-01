# backend/models/curso_video.py
from backend.models.database import db
from datetime import datetime

class CursoVideo(db.Model):
    __tablename__ = 'curso_videos'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    url = db.Column(db.Text, nullable=False)
    thumbnail = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'category': self.category,
            'url': self.url,
            'thumbnail': self.thumbnail
        }
