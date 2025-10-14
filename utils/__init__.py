# backend/utils/__init__.py
"""
Shim de compatibilidade:
Permite que 'from backend.utils ...' funcione mesmo com o pacote 'utils' na raiz.
"""

import importlib

try:
    # Reexporta a função a partir do pacote 'utils' que está na raiz do projeto
    normalize_matricula = importlib.import_module('utils.normalizer').normalize_matricula
except Exception:
    # Fallback: se preferir, mantenha uma cópia local do normalizer.
    try:
        from .normalizer import normalize_matricula  # type: ignore
    except Exception as _e:  # pragma: no cover
        raise
