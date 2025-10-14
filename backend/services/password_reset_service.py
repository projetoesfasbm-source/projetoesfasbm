# backend/services/password_reset_service.py

import os
import secrets
from datetime import datetime, timedelta, timezone
from flask import current_app
from ..models.database import db
from ..models.user import User
from ..models.password_reset_token import PasswordResetToken
from itsdangerous import SignatureExpired, BadTimeSignature

class PasswordResetService:
    DEFAULT_EXP_MINUTES = 60 # Aumentado para 1 hora

    @staticmethod
    def generate_token_for_user(user_id: int) -> str:
        """
        Gera um token de redefinição de senha seguro e com tempo de expiração.
        """
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError("Usuário não encontrado.")

        s = PasswordResetToken.get_serializer()
        # O token agora contém o ID do usuário e um salt para segurança
        return s.dumps(user.email, salt='password-reset-salt')
    
    @staticmethod
    def verify_reset_token(token: str) -> User | None:
        """
        Verifica um token de redefinição de senha e retorna o usuário se for válido.
        """
        s = PasswordResetToken.get_serializer()
        try:
            # Tenta carregar o token com o mesmo salt e tempo máximo de vida
            email = s.loads(
                token, 
                salt='password-reset-salt',
                max_age=PasswordResetService.DEFAULT_EXP_MINUTES * 60
            )
            return db.session.scalar(db.select(User).filter_by(email=email))
        except (SignatureExpired, BadTimeSignature):
            # Se o token for inválido ou expirar, retorna None
            return None

    @staticmethod
    def invalidate_token(token: str):
        """
        Invalida um token após o uso (opcional, pois o token já tem tempo de vida).
        Para uma segurança extra, poderíamos armazenar tokens usados em uma blacklist.
        Por simplicidade, o tempo de expiração já é uma boa medida.
        """
        pass