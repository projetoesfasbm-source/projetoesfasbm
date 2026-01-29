# utils/image_utils.py

import os
import uuid
import hashlib
from io import BytesIO
from werkzeug.utils import secure_filename
from flask import current_app

# Tenta importar Pillow, trata erro se não instalado (embora deva estar pelo requirements)
try:
    from PIL import Image
except ImportError:
    Image = None

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

IMAGE_MAGIC_BYTES = {
    "jpeg": [b'\xFF\xD8\xFF\xE0', b'\xFF\xD8\xFF\xE1', b'\xFF\xD8\xFF\xE8'],
    "png": [b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A'],
    "gif": [b'GIF87a', b'GIF89a'],
    "bmp": [b'BM'],
    "webp": [b'RIFF', b'WEBP'] # WEBP tem um cabeçalho RIFF, seguido por WEBP
}

class CompressedFileProxy:
    """
    Um proxy que age como um FileStorage do Werkzeug, mas contém
    os dados da imagem já comprimida em memória.
    Permite passar a imagem processada para serviços que esperam um 'file.save()'.
    """
    def __init__(self, stream, filename):
        self.stream = stream
        self.filename = filename
        # Garante que a extensão final seja .jpg, já que convertemos tudo para JPEG
        base = filename.rsplit('.', 1)[0] if '.' in filename else filename
        self.filename = f"{base}.jpg"

    def save(self, destination):
        """Salva os bytes comprimidos no caminho de destino."""
        with open(destination, 'wb') as f:
            f.write(self.stream.getvalue())

    def read(self):
        self.stream.seek(0)
        return self.stream.read()

    def seek(self, offset, whence=0):
        self.stream.seek(offset, whence)

    def tell(self):
        return self.stream.tell()
    
    @property
    def mimetype(self):
        return 'image/jpeg'

def is_image_by_magic_bytes(file_stream):
    """Verifica se o arquivo é uma imagem válida lendo seus bytes mágicos."""
    if not file_stream:
        return False
    try:
        # Salva a posição atual para restaurar depois
        pos = file_stream.tell()
        file_stream.seek(0)
        header = file_stream.read(12) 
        file_stream.seek(pos) # Restaura

        for img_type, magic_bytes_list in IMAGE_MAGIC_BYTES.items():
            for magic_bytes in magic_bytes_list:
                if img_type == "webp":
                    if header.startswith(magic_bytes[0]) and b'WEBP' in header:
                        return True
                elif header.startswith(magic_bytes):
                    return True
    except Exception:
        return False
    return False

def allowed_file(filename, file_stream=None, allowed_extensions=None):
    """
    Verifica a extensão do arquivo e os bytes mágicos para garantir que é uma imagem permitida.
    
    NOTA: Esta função foi blindada para aceitar chamadas legadas onde 'file_stream' 
    pode ser passado como a lista de extensões (ex: chamada no AssetService).
    """
    # Compatibilidade: Se o 2º argumento for uma lista/tupla, assume que são as extensões
    # e que não há stream para verificar magic bytes.
    if isinstance(file_stream, (list, tuple, set)):
        allowed_extensions = file_stream
        file_stream = None

    # 1. Verificar a extensão
    if not filename or '.' not in filename:
        return False
        
    if allowed_extensions:
        ext = filename.rsplit('.', 1)[1].lower()
        if ext not in allowed_extensions:
            return False

    # 2. Verificar os bytes mágicos (apenas se o stream for fornecido e válido)
    if file_stream:
        if not is_image_by_magic_bytes(file_stream):
            return False

    return True

def generate_unique_filename(filename):
    """Gera um nome único para o arquivo"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'jpg'
    unique_id = str(uuid.uuid4())
    return f"{unique_id}.{ext}"

def get_file_hash(file_path):
    """Gera hash MD5 do arquivo para verificar duplicatas"""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except FileNotFoundError:
        return None

def optimize_image(file_path, max_width=1920, max_height=1080, quality=90):
    """
    Otimiza a imagem existente no disco (Redimensiona e Comprime).
    Usado pelo AssetService.
    """
    if not Image:
        current_app.logger.warning("AVISO: A biblioteca 'Pillow' não está instalada. Pulando otimização de imagem.")
        return True

    try:
        if file_path.lower().endswith('.svg'):
            return True

        with Image.open(file_path) as img:
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            if img.width > max_width or img.height > max_height:
                img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            img.save(file_path, 'JPEG', quality=quality, optimize=True)
            
        return True
    except Exception as e:
        current_app.logger.error(f"Erro ao otimizar imagem {file_path}: {e}")
        return False

def compress_image_to_memory(file_storage, max_size=(256, 256), quality=60):
    """
    Lê uma imagem de um FileStorage, redimensiona, converte para RGB (JPEG)
    e retorna um objeto CompressedFileProxy pronto para ser salvo.
    
    Usado para: Fotos de Perfil e Assinaturas (onde o tamanho deve ser pequeno).
    """
    if not Image:
        print("Pillow não instalado, ignorando compressão.")
        return None

    try:
        # Abre a imagem usando Pillow
        img = Image.open(file_storage)
        
        # Converte para RGB (remove transparência de PNG/WebP para salvar como JPEG)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
            
        # Redimensiona mantendo a proporção (thumbnail)
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Salva em um buffer de memória como JPEG otimizado
        output_buffer = BytesIO()
        img.save(output_buffer, format='JPEG', quality=quality, optimize=True)
        output_buffer.seek(0)
        
        return CompressedFileProxy(output_buffer, file_storage.filename)
        
    except Exception as e:
        print(f"Erro ao comprimir imagem: {e}")
        return None