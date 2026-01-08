# backend/models/instrutor.py

from __future__ import annotations
from datetime import datetime, timezone
import typing as t

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import db

if t.TYPE_CHECKING:
    from .user import User
    from .school import School


class Instrutor(db.Model):
    __tablename__ = "instrutores"

    id: Mapped[int] = mapped_column(primary_key=True)

    telefone: Mapped[t.Optional[str]] = mapped_column(db.String(20), nullable=True)
    is_rr: Mapped[bool] = mapped_column(default=False, nullable=False)
    
    foto_perfil: Mapped[t.Optional[str]] = mapped_column(db.String(255), default='default.png')

    # CORREÇÃO: Removido unique=True daqui. 
    # Um usuário pode ser instrutor em várias escolas (linhas diferentes), 
    # mas apenas uma vez por escola (garantido pelo UniqueConstraint abaixo).
    user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"), nullable=False)
    
    school_id: Mapped[int] = mapped_column(db.ForeignKey("schools.id"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        onupdate=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="instrutor_profile")
    school: Mapped["School"] = relationship("School")

    # Esta é a restrição correta: Único par User+School
    __table_args__ = (
        db.UniqueConstraint("user_id", "school_id", name="uq_instrutor_user_school"),
    )

    def __repr__(self) -> str:
        return f"<Instrutor user_id={self.user_id} school_id={self.school_id}>"