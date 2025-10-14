import os
from flask import current_app
from werkzeug.utils import secure_filename
from sqlalchemy import select

from ..models.database import db
from ..models.image_asset import ImageAsset
from utils.image_utils import allowed_file, generate_unique_filename, optimize_image

class AssetService:
    ALLOWED_EXTENSIONS = ['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp']
    MAX_FILE_SIZE = 5 * 1024 * 1024 # 5 MB

    @staticmethod
    def initialize_upload_folder(app):
        AssetService.UPLOAD_FOLDER = os.path.join(app.root_path, '..', 'static', 'uploads')

    @staticmethod
    def get_all_assets():
        return db.session.scalars(select(ImageAsset).order_by(ImageAsset.created_at.desc())).all()

    @staticmethod
    def upload_asset(file, asset_type, category, description, uploaded_by_user_id):
        if file.filename == '':
            return False, 'Nenhum arquivo selecionado.'
        
        if not allowed_file(file.filename, AssetService.ALLOWED_EXTENSIONS):
            return False, 'Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF, SVG, WEBP.'

        # Basic MIME type check (can be more robust)
        # Note: This is a basic check and can be spoofed. For critical applications, deeper content inspection is needed.
        mimetype = file.mimetype
        if not mimetype or not any(ext in mimetype for ext in AssetService.ALLOWED_EXTENSIONS):
             # Fallback for SVG which might have 'image/svg+xml'
            if not (file.filename.lower().endswith('.svg') and mimetype == 'image/svg+xml'):
                return False, 'Tipo de conteúdo do arquivo não permitido.'

        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0) # Reset file pointer

        if file_size > AssetService.MAX_FILE_SIZE:
            return False, f'Arquivo muito grande. Tamanho máximo permitido é {AssetService.MAX_FILE_SIZE / (1024 * 1024)} MB.'

        try:
            os.makedirs(AssetService.UPLOAD_FOLDER, exist_ok=True)
            
            original_filename = secure_filename(file.filename)
            unique_filename = generate_unique_filename(original_filename)
            file_path = os.path.join(AssetService.UPLOAD_FOLDER, unique_filename)
            
            file.save(file_path)
            
            if not unique_filename.lower().endswith('.svg'):
                optimize_image(file_path)
            
            new_asset = ImageAsset(
                filename=unique_filename,
                original_filename=original_filename,
                asset_type=asset_type,
                category=category,
                description=description,
                uploaded_by=uploaded_by_user_id
            )
            
            db.session.add(new_asset)
            db.session.commit()
            
            return True, f'Asset "{original_filename}" enviado com sucesso!'
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao fazer upload de asset: {e}")
            return False, f'Erro ao fazer upload: {str(e)}'

    @staticmethod
    def delete_asset(asset_id):
        asset = db.session.get(ImageAsset, asset_id)
        if not asset:
            return False, 'Asset não encontrado.'
        
        try:
            file_path = os.path.join(AssetService.UPLOAD_FOLDER, asset.filename)
            if os.path.exists(file_path):
                os.remove(file_path)
            
            db.session.delete(asset)
            db.session.commit()
            
            return True, 'Asset deletado com sucesso!'
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao deletar asset: {e}")
            return False, f'Erro ao deletar asset: {str(e)}'

    @staticmethod
    def toggle_asset_status(asset_id):
        asset = db.session.get(ImageAsset, asset_id)
        if not asset:
            return False, 'Asset não encontrado.'
        
        try:
            asset.is_active = not asset.is_active
            db.session.commit()
            
            status = 'ativado' if asset.is_active else 'desativado'
            return True, f'Asset {status} com sucesso!'
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao ativar/desativar asset: {e}")
            return False, f'Erro: {str(e)}'

    @staticmethod
    def list_assets_by_type(asset_type):
        assets = db.session.scalars(select(ImageAsset).filter_by(
            asset_type=asset_type, 
            is_active=True
        )).all()
        
        return [{
            'id': asset.id,
            'filename': asset.filename,
            'original_filename': asset.original_filename,
            'url': url_for('static', filename=f'uploads/{asset.filename}') # url_for needs app context
        } for asset in assets]
