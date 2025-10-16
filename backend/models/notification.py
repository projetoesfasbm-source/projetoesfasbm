# backend/models/notification.py
from __future__ import annotations
import typing as t
from datetime import datetime, timezone
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship

if t.TYPE_CHECKING:
    from .user import User

class Notification(db.Model):
    __tablename__ = 'notifications'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey('users.id'), nullable=False)
    message: Mapped[str] = mapped_column(db.String(255), nullable=False)
    url: Mapped[t.Optional[str]] = mapped_column(db.String(255))
    is_read: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    user: Mapped["User"] = relationship(back_populates="notifications")

    def __repr__(self):
        return f"<Notification id={self.id} user_id={self.user_id} read={self.is_read}>"