# backend/models/user_role.py

from __future__ import annotations
import typing as t
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import db

if t.TYPE_CHECKING:
    from .user import User
    from .school import School

class UserRole(db.Model):
    __tablename__ = "user_roles"

    id: Mapped[int] = mapped_column(primary_key=True)

    # FK para o usuário
    user_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    
    # FK para a escola
    school_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    
    # O papel específico nesta escola (ex: 'admin_sens', 'admin_cal', 'instrutor')
    role: Mapped[str] = mapped_column(db.String(20), nullable=False)

    # Relacionamentos
    user: Mapped["User"] = relationship("User", back_populates="roles")
    school: Mapped["School"] = relationship("School", back_populates="user_roles")

    def __repr__(self):
        return f"<UserRole {self.user_id}-{self.role}@{self.school_id}>"