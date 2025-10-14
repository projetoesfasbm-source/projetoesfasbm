import re

def validate_username(username: str) -> bool:
    """Valida o nome de usuário (alfanuméricos, 3-20 caracteres)."""
    return 3 <= len(username) <= 20 and username.isalnum()

def validate_email(email: str) -> bool:
    """Valida o formato de um e-mail."""
    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(email_regex, email) is not None

def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Verifica a força da senha.
    Requer: 8+ caracteres, 1 maiúscula, 1 minúscula, 1 número, 1 caractere especial.
    """
    if len(password) < 8:
        return False, "A senha deve ter pelo menos 8 caracteres."
    if not re.search(r"[A-Z]", password):
        return False, "A senha deve conter pelo menos uma letra maiúscula."
    if not re.search(r"[a-z]", password):
        return False, "A senha deve conter pelo menos uma letra minúscula."
    if not re.search(r"\d", password):
        return False, "A senha deve conter pelo menos um número."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "A senha deve conter pelo menos um caractere especial."
    return True, "Senha forte."

def validate_cpf(cpf: str) -> bool:
    """Valida o formato de um CPF (XXX.XXX.XXX-XX) após limpeza."""
    cpf_clean = re.sub(r'\D', '', cpf)
    if not re.match(r"^\d{11}$", cpf_clean):
        return False
    return True

def validate_telefone(telefone: str) -> bool:
    """Valida o formato de um telefone (XX) XXXXX-XXXX) após limpeza."""
    telefone_clean = re.sub(r'\D', '', telefone)
    if not re.match(r"^\d{10,11}$", telefone_clean):
        return False
    return True