# backend/services/totp_service.py
import pyotp

class TotpService:
    """
    Serviço responsável por gerenciar a Autenticação em Duas Etapas (2FA)
    utilizando o algoritmo TOTP (Google Authenticator, Authy, etc).
    """

    @staticmethod
    def generate_secret() -> str:
        """Gera um novo segredo base32 aleatório para o usuário."""
        return pyotp.random_base32()

    @staticmethod
    def get_provisioning_uri(secret: str, user_identifier: str, issuer_name: str = "ESFASBM") -> str:
        """
        Gera a URI de provisionamento que será embutida no QR Code.
        
        :param secret: A chave secreta do usuário.
        :param user_identifier: Identificador do usuário (ex: matrícula ou e-mail).
        :param issuer_name: Nome do sistema exibido no app (padrão: ESFASBM).
        """
        if not secret:
            return ""
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=user_identifier, issuer_name=issuer_name)

    @staticmethod
    def verify_token(secret: str, token: str) -> bool:
        """Verifica se o token numérico (6 dígitos) fornecido é válido."""
        if not secret or not token:
            return False
        totp = pyotp.TOTP(secret)
        return totp.verify(token)
