# backend/extensions.py

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# --- CONFIGURAÇÃO DE LIMITES ADICIONADA AQUI ---
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://", # Define explicitamente a memória para remover o aviso do log
    # default_limits=["200 per minute"], # COMENTADO PARA EVITAR ESTOURO DE MEMÓRIA (OOM) NO RENDER
)