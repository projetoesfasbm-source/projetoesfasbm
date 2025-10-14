from flask_login import login_user, logout_user, current_user
from sqlalchemy import select
from ..models.database import db
from ..models.user import User
from utils.validators import validate_username, validate_email, validate_password_strength

class AuthService:
    @staticmethod
    def login(username, password):
        stmt = select(User).where(User.username == username)
        user = db.session.scalar(stmt)

        if user and user.check_password(password) and getattr(user, 'is_active', False):
            login_user(user)
            return user
        return None

    @staticmethod
    def logout():
        logout_user()

    @staticmethod
    def is_admin():
        return current_user.is_authenticated and getattr(current_user, 'role', None) == 'super_admin'