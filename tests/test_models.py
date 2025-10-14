# tests/test_models.py

import pytest
from backend.models.user import User

class TestUserModel:
    """
    Suíte de testes para o modelo User.
    """

    def test_password_hashing(self):
        """
        Testa se o hashing e a verificação de senhas estão funcionando corretamente.

        Este teste garante que:
        1. A senha de um usuário não é armazenada em texto plano.
        2. A função check_password retorna True para a senha correta.
        3. A função check_password retorna False para uma senha incorreta.
        """
        # 1. Setup: Cria uma instância de User
        u = User(username='testuser', id_func='12345')

        # 2. Ação: Define uma senha
        u.set_password('minhaSenhaForte123!')

        # 3. Asserções (Verificações)
        # Garante que o password_hash não está vazio e não é a senha original
        assert u.password_hash is not None
        assert u.password_hash != 'minhaSenhaForte123!'

        # Garante que a verificação funciona para a senha correta
        assert u.check_password('minhaSenhaForte123!') is True

        # Garante que a verificação falha para uma senha incorreta
        assert u.check_password('senhaErrada') is False