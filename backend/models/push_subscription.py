# backend/models/push_subscription.py
from __future__ import annotations
import typing as t
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship

if t.TYPE_CHECKING:
    from .user import User

class PushSubscription(db.Model):
    __tablename__ = 'push_subscriptions'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey('users.id'), nullable=False)
    # O fcm_token é o "endereço" do dispositivo para receber notificações
    fcm_token: Mapped[str] = mapped_column(db.String(255), unique=True, nullable=False)

    user: Mapped["User"] = relationship(back_populates="push_subscriptions")

    def __repr__(self):
        return f"<PushSubscription id={self.id} user_id={self.user_id}>"