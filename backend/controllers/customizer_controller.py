# backend/controllers/customizer_controller.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from ..models.database import db
from ..models.image_asset import ImageAsset
from ..models.site_config import SiteConfig
from ..services.site_config_service import SiteConfigService
from utils.decorators import admin_or_programmer_required
from ..services.asset_service import AssetService

customizer_bp = Blueprint('customizer', __name__, url_prefix='/customizer')

@customizer_bp.route('/')
@login_required
@admin_or_programmer_required
def index():
    """Painel principal de customização"""
    SiteConfigService.init_default_configs()
    db.session.commit()
    
    configs = SiteConfigService.get_all_configs()
    assets = AssetService.get_all_assets()
    
    configs_by_category = {}
    for config in configs:
        if config.category not in configs_by_category:
            configs_by_category[config.category] = []
        configs_by_category[config.category].append(config)
    
    return render_template('customizer/index.html', 
                         configs_by_category=configs_by_category, 
                         assets=assets)

@customizer_bp.route('/update', methods=['POST'])
@login_required
@admin_or_programmer_required
def update_config():
    """Atualiza uma configuração"""
    config_key = request.form.get('config_key')
    config_value = request.form.get('config_value')
    config_type = request.form.get('config_type', 'text')
    
    if not config_key:
        return jsonify({'success': False, 'message': 'Chave de configuração não fornecida'})
    
    try:
        SiteConfigService.set_config(
            key=config_key,
            value=config_value,
            config_type=config_type,
            updated_by=current_user.id
        )
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Configuração atualizada com sucesso!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'})

@customizer_bp.route('/preview')
@login_required
@admin_or_programmer_required
def preview():
    """Preview das configurações"""
    configs = SiteConfigService.get_all_configs()
    config_dict = {config.config_key: config.config_value for config in configs}
    
    return render_template('customizer/preview.html', configs=config_dict)

@customizer_bp.route('/reset', methods=['POST'])
@login_required
@admin_or_programmer_required
def reset_configs():
    """Reset todas as configurações para padrão"""
    try:
        SiteConfigService.delete_all_configs()
        db.session.commit()
        
        SiteConfigService.init_default_configs()
        db.session.commit()
        
        flash('Configurações resetadas para o padrão!', 'success')
        return redirect(url_for('customizer.index'))
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao resetar configurações: {str(e)}', 'error')
        return redirect(url_for('customizer.index'))