# backend/models/password_reset_token.py

from __future__ import annotations
import typing as t
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship
import secrets # --- NOVA IMPORTAÇÃO ---
from itsdangerous import URLSafeTimedSerializer
from flask import current_app

if t.TYPE_CHECKING:
    from .user import User

class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_tokens'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey('users.id'), nullable=False)
    
    # --- CAMPO REMOVIDO, O TOKEN SERÁ GERADO DE OUTRA FORMA ---
    # token_hash: Mapped[str] = mapped_column(db.String(256), nullable=False)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    used_at: Mapped[t.Optional[datetime]] = mapped_column(nullable=True)
    
    # --- CAMPOS REMOVIDOS ---
    # attempts: Mapped[int] = mapped_column(default=0)
    # max_attempts: Mapped[int] = mapped_column(default=5)
    
    revoked: Mapped[bool] = mapped_column(default=False)
    created_by_admin_id: Mapped[t.Optional[int]] = mapped_column(db.ForeignKey('users.id'), nullable=True)

    user: Mapped['User'] = relationship('User', foreign_keys=[user_id])
    created_by_admin: Mapped[t.Optional['User']] = relationship('User', foreign_keys=[created_by_admin_id])

    # --- MÉTODOS ATUALIZADOS E NOVOS ---
    @staticmethod
    def get_serializer() -> URLSafeTimedSerializer:
        return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    def is_usable(self) -> bool:
        return (not self.revoked) and (self.used_at is None) and (not self.is_expired())