# backend/controllers/customizer_controller.py

from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from ..services.site_config_service import SiteConfigService
from ..services.user_service import UserService
from utils.decorators import admin_or_programmer_required

customizer_bp = Blueprint('customizer', __name__, url_prefix='/customizer')

@customizer_bp.route('/', methods=['GET'])
@login_required
@admin_or_programmer_required
def index():
    # Obtém a escola ativa
    school_id = UserService.get_current_school_id()
    
    # Obtém todas as configurações base (definições globais para saber categorias e labels)
    all_base_configs = SiteConfigService.get_all_configs()
    
    # Reconstrói a estrutura 'configs_by_category' que o template espera
    configs_by_category = {}
    
    for config in all_base_configs:
        # Para cada configuração, buscamos o valor REAL (contexto escola ou global)
        # em vez de usar o valor cru que veio do get_all_configs (que pode ser o global)
        real_value = SiteConfigService.get_config(config.config_key, config.config_value, school_id=school_id)
        
        # Cria um objeto temporário ou atualiza o valor para exibição
        # Precisamos garantir que o template receba objetos com atributos .config_key, .description, etc.
        config_display = {
            'config_key': config.config_key,
            'config_value': real_value, # Valor contextualizado!
            'config_type': config.config_type,
            'description': config.description,
            'category': config.category
        }
        
        category = config.category or 'general'
        if category not in configs_by_category:
            configs_by_category[category] = []
        configs_by_category[category].append(config_display)

    # O template espera 'configs_by_category'
    return render_template('customizer/index.html', configs_by_category=configs_by_category)

@customizer_bp.route('/update', methods=['POST'])
@login_required
@admin_or_programmer_required
def update():
    school_id = UserService.get_current_school_id()
    
    if not school_id and not current_user.is_programador:
        flash("Selecione uma escola para personalizar os horários.", "warning")
        return redirect(url_for('customizer.index'))

    # Itera sobre todos os campos enviados no formulário
    # O form envia chaves dinâmicas baseadas no config_key
    try:
        # Obtemos a lista de chaves válidas para não salvar lixo
        valid_keys = [c.config_key for c in SiteConfigService.get_all_configs()]
        
        for key, value in request.form.items():
            if key in valid_keys:
                SiteConfigService.set_config(key, value, school_id=school_id)
        
        flash('Configurações atualizadas com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao atualizar configurações: {e}', 'danger')

    return redirect(url_for('customizer.index'))

@customizer_bp.route('/reset', methods=['POST'])
@login_required
@admin_or_programmer_required
def reset_configs():
    """
    Reseta as configurações de horário (ou todas da categoria 'horarios').
    """
    school_id = UserService.get_current_school_id()
    
    # Identifica chaves de horário para resetar
    horario_configs = SiteConfigService.get_configs_by_category('horarios')
    keys_to_reset = [c.config_key for c in horario_configs]

    try:
        for key in keys_to_reset:
            SiteConfigService.delete_config(key, school_id=school_id)
            
        target = "da escola" if school_id else "globais"
        flash(f'Configurações de horário {target} foram resetadas.', 'success')
    except Exception as e:
        flash(f'Erro ao resetar configurações: {e}', 'danger')

    return redirect(url_for('customizer.index'))

@customizer_bp.route('/preview')
@login_required
@admin_or_programmer_required
def preview():
    school_id = UserService.get_current_school_id()
    
    configs = {
        'horario_periodo_01': SiteConfigService.get_config('horario_periodo_01', '08:00', school_id=school_id),
        'horario_intervalo_manha': SiteConfigService.get_config('horario_intervalo_manha', '09:40 - 10:00', school_id=school_id),
    }
    return render_template('customizer/preview.html', configs=configs)