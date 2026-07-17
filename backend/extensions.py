# backend/extensions.py

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

# --- CONFIGURAÇÃO DE LIMITES ADICIONADA AQUI ---
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://", # Define explicitamente a memória para remover o aviso do log
)

csrf = CSRFProtect()