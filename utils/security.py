from werkzeug.security import generate_password_hash, check_password_hash
import re

def hash_password(password):
    return generate_password_hash(password, method='pbkdf2:sha256')

def check_password(password, password_hash):
    return check_password_hash(password_hash, password)

def validate_password_strength(password):
    if len(password) < 8:
        return False, "Senha deve ter pelo menos 8 caracteres"
    if not re.search(r'[A-Z]', password):
        return False, "Senha deve conter pelo menos uma letra maiúscula"
    if not re.search(r'[a-z]', password):
        return False, "Senha deve conter pelo menos uma letra minúscula"
    if not re.search(r'[0-9]', password):
        return False, "Senha deve conter pelo menos um número"
    return True, "Senha forte"