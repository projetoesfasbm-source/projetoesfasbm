import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from ..models.database import db
from ..models.image_asset import ImageAsset
# --- PERMISSÃO ALTERADA AQUI ---
from utils.decorators import admin_or_programmer_required
from utils.image_utils import allowed_file, generate_unique_filename, optimize_image, get_file_hash

assets_bp = Blueprint('assets', __name__, url_prefix='/assets')

@assets_bp.route('/manage')
@login_required
@admin_or_programmer_required
def manage_assets():
    """Página principal de gerenciamento de assets"""
    assets = db.session.query(ImageAsset).order_by(ImageAsset.created_at.desc()).all()
    return render_template('manage_assets.html', assets=assets)

@assets_bp.route('/upload', methods=['GET', 'POST'])
@login_required
@admin_or_programmer_required
def upload_asset():
    """Upload de nova imagem/asset"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Nenhum arquivo selecionado.', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        asset_type = request.form.get('asset_type')
        category = request.form.get('category')
        description = request.form.get('description', '')
        
        if file.filename == '':
            flash('Nenhum arquivo selecionado.', 'error')
            return redirect(request.url)
        
        ALLOWED_ASSET_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'}
        
        file.stream.seek(0)
        if not allowed_file(file.filename, file.stream, ALLOWED_ASSET_EXTENSIONS):
            flash('Tipo de arquivo não permitido. Use: PNG, JPG, JPEG, GIF, SVG, WEBP', 'error')
            return redirect(request.url)
        
        try:
            upload_folder = os.path.join(current_app.root_path, '..', 'static', 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            
            original_filename = secure_filename(file.filename)
            unique_filename = generate_unique_filename(original_filename)
            file_path = os.path.join(upload_folder, unique_filename)
            
            file.save(file_path)
            
            if not unique_filename.lower().endswith('.svg'):
                optimize_image(file_path)
            
            new_asset = ImageAsset(
                filename=unique_filename,
                original_filename=original_filename,
                asset_type=asset_type,
                category=category,
                description=description,
                uploaded_by=current_user.id
            )
            
            db.session.add(new_asset)
            db.session.commit()
            
            flash(f'Asset "{original_filename}" enviado com sucesso!', 'success')
            return redirect(url_for('assets.manage_assets'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao fazer upload: {str(e)}', 'error')
            return redirect(request.url)
    
    return render_template('upload_asset.html')

@assets_bp.route('/delete/<int:asset_id>', methods=['POST'])
@login_required
@admin_or_programmer_required
def delete_asset(asset_id):
    """Deletar asset"""
    asset = db.session.get(ImageAsset, asset_id)
    if not asset:
        flash('Asset não encontrado.', 'error')
        return redirect(url_for('assets.manage_assets'))
    
    try:
        file_path = os.path.join(current_app.root_path, '..', 'static', 'uploads', asset.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        db.session.delete(asset)
        db.session.commit()
        
        flash('Asset deletado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao deletar asset: {str(e)}', 'error')
    
    return redirect(url_for('assets.manage_assets'))

@assets_bp.route('/toggle/<int:asset_id>', methods=['POST'])
@login_required
@admin_or_programmer_required
def toggle_asset(asset_id):
    """Ativar/desativar asset"""
    asset = db.session.get(ImageAsset, asset_id)
    if not asset:
        return jsonify({'success': False, 'message': 'Asset não encontrado'})
    
    try:
        asset.is_active = not asset.is_active
        db.session.commit()
        
        status = 'ativado' if asset.is_active else 'desativado'
        return jsonify({'success': True, 'message': f'Asset {status} com sucesso!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'})

@assets_bp.route('/api/list/<asset_type>')
@login_required
@admin_or_programmer_required
def api_list_assets(asset_type):
    """API para listar assets por tipo"""
    assets = db.session.query(ImageAsset).filter_by(
        asset_type=asset_type, 
        is_active=True
    ).all()
    
    return jsonify([{
        'id': asset.id,
        'filename': asset.filename,
        'original_filename': asset.original_filename,
        'url': url_for('static', filename=f'uploads/{asset.filename}')
    } for asset in assets])