# backend/models/user_school.py
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import db
from datetime import datetime

class UserSchool(db.Model):
    __tablename__ = 'user_schools'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    school_id: Mapped[int] = mapped_column(ForeignKey('schools.id'), nullable=False)
    role: Mapped[str] = mapped_column(db.String(50), nullable=False, default='aluno')
    
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamentos
    user = relationship("User", back_populates="user_schools")
    school = relationship("School", back_populates="user_schools")

    __table_args__ = (
        UniqueConstraint('user_id', 'school_id', name='uq_user_school'),
    )