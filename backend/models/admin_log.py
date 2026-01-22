# backend/models/admin_log.py
from datetime import datetime
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Integer, String, Text, DateTime

class AdminLog(db.Model):
    __tablename__ = 'admin_logs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey('schools.id'), nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=True)  # Pode armazenar JSON ou Texto simples
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    
    # Suporte para Logs em Cascata (Hierarquia)
    parent_id: Mapped[int] = mapped_column(ForeignKey('admin_logs.id'), nullable=True)
    children = relationship('AdminLog', backref=db.backref('parent', remote_side=[id]), cascade="all, delete-orphan")
    
    user = relationship("User", backref="logs")
    school = relationship("School", backref="logs")

    def __repr__(self):
        return f"<AdminLog {self.action} by User {self.user_id} at {self.timestamp}>"