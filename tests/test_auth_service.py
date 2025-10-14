# tests/test_auth_service.py

import pytest
from flask_login import current_user
from backend.services.auth_service import AuthService
from backend.models.user import User
from backend.models.database import db

class TestAuthService:
    """
    Suíte de testes para o AuthService.
    """

    def test_login_success(self, test_app, new_user):
        """Testa o login com credenciais válidas."""
        with test_app.test_request_context():
            # Ação
            user = AuthService.login(new_user.username, 'password123')

            # Asserções
            assert user is not None
            assert user.username == new_user.username
            assert current_user.is_authenticated
            assert current_user.id == new_user.id

    def test_login_invalid_password(self, test_app, new_user):
        """Testa o login com senha inválida."""
        with test_app.test_request_context():
            # Ação
            user = AuthService.login(new_user.username, 'wrongpassword')

            # Asserções
            assert user is None
            assert not current_user.is_authenticated

    def test_login_inactive_user(self, test_app, new_user):
        """Testa o login de um usuário inativo."""
        with test_app.test_request_context():
            new_user.is_active = False
            db.session.commit()

            # Ação
            user = AuthService.login(new_user.username, 'password123')

            # Asserções
            assert user is None
            assert not current_user.is_authenticated

    def test_logout(self, test_app, logged_in_user):
        """Testa se o logout desconecta o usuário."""
        with test_app.test_request_context():
            assert current_user.is_authenticated

            # Ação
            AuthService.logout()

            # Asserções
            assert not current_user.is_authenticated

    def test_is_admin_when_super_admin(self, test_app, logged_in_super_admin):
        """Testa se is_admin retorna True para super_admin."""
        with test_app.test_request_context():
            # Ação e Asserção
            assert AuthService.is_admin() is True

    def test_is_admin_when_not_admin(self, test_app, logged_in_user):
        """Testa se is_admin retorna False para usuários comuns."""
        with test_app.test_request_context():
            # Ação e Asserção
            assert AuthService.is_admin() is False

    def test_is_admin_when_logged_out(self, test_app):
        """Testa se is_admin retorna False quando ninguém está logado."""
        with test_app.test_request_context():
            # Ação e Asserção
            assert AuthService.is_admin() is False
