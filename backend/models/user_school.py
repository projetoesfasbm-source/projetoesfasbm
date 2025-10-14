# backend/models/user_school.py

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import db

class UserSchool(db.Model):
    __tablename__ = 'user_schools'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey('users.id'), nullable=False)
    school_id: Mapped[int] = mapped_column(db.ForeignKey('schools.id'), nullable=False)
    role: Mapped[str] = mapped_column(db.String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        onupdate=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    # relacionamentos SEM overlaps (cada lado só “enxerga” UserSchool)
    user: Mapped['User'] = relationship('User', back_populates='user_schools')
    school: Mapped['School'] = relationship('School', back_populates='user_schools')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'school_id', name='uq_user_school'),
    )

    def __repr__(self) -> str:
        return f"<UserSchool user_id={self.user_id} school_id={self.school_id} role={self.role}>"
