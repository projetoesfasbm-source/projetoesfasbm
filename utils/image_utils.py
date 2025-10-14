import os
import uuid
from werkzeug.utils import secure_filename
import hashlib
from flask import current_app

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

IMAGE_MAGIC_BYTES = {
    "jpeg": [b'\xFF\xD8\xFF\xE0', b'\xFF\xD8\xFF\xE1', b'\xFF\xD8\xFF\xE8'],
    "png": [b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A'],
    "gif": [b'GIF87a', b'GIF89a'],
    "bmp": [b'BM'],
    "webp": [b'RIFF', b'WEBP'] # WEBP tem um cabeçalho RIFF, seguido por WEBP
}

def is_image_by_magic_bytes(file_stream):
    """Verifica se o arquivo é uma imagem válida lendo seus bytes mágicos."""
    header = file_stream.read(12) # Ler os primeiros 12 bytes para cobrir a maioria dos casos
    file_stream.seek(0) # Voltar ao início do stream

    for img_type, magic_bytes_list in IMAGE_MAGIC_BYTES.items():
        for magic_bytes in magic_bytes_list:
            if img_type == "webp":
                # Para WebP, precisamos verificar o cabeçalho RIFF e depois 'WEBP' mais adiante
                if header.startswith(magic_bytes[0]) and b'WEBP' in header:
                    return True
            elif header.startswith(magic_bytes):
                return True
    return False

def allowed_file(filename, file_stream, allowed_extensions):
    """Verifica a extensão do arquivo e os bytes mágicos para garantir que é uma imagem permitida."""
    # 1. Verificar a extensão
    if not ('.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions):
        return False

    # 2. Verificar os bytes mágicos
    if not is_image_by_magic_bytes(file_stream):
        return False

    return True

def generate_unique_filename(filename):
    """Gera um nome único para o arquivo"""
    ext = filename.rsplit('.', 1)[1].lower()
    unique_id = str(uuid.uuid4())
    return f"{unique_id}.{ext}"

def optimize_image(file_path, max_width=1920, max_height=1080, quality=90):
    """
    Otimiza a imagem redimensionando e comprimindo.
    - LARGURA MÁXIMA AUMENTADA PARA 1920px PARA BANNERS DE ALTA QUALIDADE.
    - QUALIDADE AUMENTADA PARA 90.
    """
    try:
        from PIL import Image
        
        if file_path.lower().endswith('.svg'):
            return True

        with Image.open(file_path) as img:
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            if img.width > max_width or img.height > max_height:
                img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            img.save(file_path, 'JPEG', quality=quality, optimize=True)
            
        return True
    except ImportError:
        current_app.logger.warning("AVISO: A biblioteca 'Pillow' não está instalada. Pulando otimização de imagem.")
        return True
    except Exception as e:
        current_app.logger.error(f"Erro ao otimizar imagem {file_path}: {e}")
        return False

def get_file_hash(file_path):
    """Gera hash MD5 do arquivo para verificar duplicatas"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()
