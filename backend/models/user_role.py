# backend/models/user_role.py
from __future__ import annotations
import typing as t
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import db

if t.TYPE_CHECKING:
    from .user import User

class UserRole(db.Model):
    __tablename__ = 'user_roles'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey('users.id'), nullable=False)
    role_name: Mapped[str] = mapped_column(db.String(50), nullable=False)

    # Relacionamento comentado para evitar erro de Mapper já que User não tem mais 'roles'
    # user: Mapped["User"] = relationship("User", back_populates="roles")

    def __repr__(self):
        return f'<UserRole {self.role_name} for User {self.user_id}>'