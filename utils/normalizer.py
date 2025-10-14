# utils/normalizer.py
import re
from typing import Optional

def normalize_matricula(text: Optional[str]) -> Optional[str]:
    """
    Mantém apenas dígitos na matrícula e valida o comprimento.
    Retorna a matrícula normalizada se tiver entre 1 e 7 dígitos.
    Retorna None caso contrário.
    """
    if not text:
        return None
    only_digits = re.sub(r"\D+", "", text.strip())
    # Valida se o resultado contém apenas números e tem no máximo 7 dígitos
    if only_digits and len(only_digits) <= 7:
        return only_digits
    return None

def normalize_name(name: Optional[str]) -> Optional[str]:
    """
    Formata um nome para o formato de Título (Primeiras Letras Maiúsculas).
    Exemplo: "joão da SILVA" -> "João Da Silva"
    """
    if not name:
        return None
    # Converte para minúsculas e depois aplica o title() para capitalizar cada palavra.
    return name.strip().lower().title()