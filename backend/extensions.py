# backend/extensions.py

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# --- CONFIGURAÇÃO DE LIMITES ADICIONADA AQUI ---
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per minute"],  # Limite padrão para todos os endpoints
)