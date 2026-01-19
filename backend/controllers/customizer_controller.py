# backend/controllers/customizer_controller.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
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
        # Pula configurações que já são personalizações de escola (começam com school_)
        # para evitar duplicidade na listagem base
        if config.config_key.startswith('school_'):
            continue

        # Para cada configuração base, buscamos o valor REAL (contexto escola ou global)
        real_value = SiteConfigService.get_config(config.config_key, config.config_value, school_id=school_id)
        
        config_display = {
            'config_key': config.config_key,
            'config_value': real_value, # Valor contextualizado (da escola se existir)
            'config_type': config.config_type,
            'description': config.description,
            'category': config.category
        }
        
        category = config.category or 'general'
        if category not in configs_by_category:
            configs_by_category[category] = []
        configs_by_category[category].append(config_display)

    return render_template('customizer/index.html', configs_by_category=configs_by_category)

@customizer_bp.route('/update', methods=['POST'])
@login_required
@admin_or_programmer_required
def update():
    """
    Atualiza configurações. Retorna JSON para evitar erros no frontend.
    """
    school_id = UserService.get_current_school_id()
    
    if not school_id and not current_user.is_programador:
        return jsonify({'success': False, 'message': 'Selecione uma escola para personalizar os horários.'}), 400

    try:
        # Obtemos a lista de chaves base válidas para validar o input
        # Filtramos para pegar apenas as chaves originais (sem prefixo school_)
        all_configs = SiteConfigService.get_all_configs()
        valid_keys = set()
        for c in all_configs:
            # Se for uma config de escola, extraímos a chave base, senão usamos a chave direta
            if c.config_key.startswith('school_'):
                parts = c.config_key.split('_', 2) # school, id, key
                if len(parts) > 2:
                    valid_keys.add(parts[2])
            else:
                valid_keys.add(c.config_key)
        
        updated_count = 0
        
        for key, value in request.form.items():
            # O formulário envia a chave base (ex: 'horario_periodo_01')
            if key in valid_keys:
                # O Service trata de adicionar o prefixo school_{id}_ automaticamente
                SiteConfigService.set_config(key, value, school_id=school_id)
                updated_count += 1
        
        if updated_count == 0:
             return jsonify({'success': False, 'message': 'Nenhuma configuração válida encontrada para atualizar.'}), 400

        return jsonify({'success': True, 'message': 'Configurações atualizadas com sucesso!'})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Erro ao atualizar configurações: {str(e)}'}), 500

@customizer_bp.route('/reset', methods=['POST'])
@login_required
@admin_or_programmer_required
def reset_configs():
    """
    Reseta as configurações de horário. Retorna JSON.
    """
    school_id = UserService.get_current_school_id()
    
    try:
        # Identifica chaves de horário para resetar
        horario_configs = SiteConfigService.get_configs_by_category('horarios')
        
        # Filtra apenas chaves base
        keys_to_reset = []
        for c in horario_configs:
            if not c.config_key.startswith('school_'):
                keys_to_reset.append(c.config_key)

        if not keys_to_reset:
             return jsonify({'success': False, 'message': 'Nenhuma configuração de horário encontrada.'}), 404

        for key in keys_to_reset:
            # O delete_config trata a remoção da chave com prefixo da escola
            SiteConfigService.delete_config(key, school_id=school_id)
            
        target = "da escola" if school_id else "globais"
        return jsonify({'success': True, 'message': f'Configurações de horário {target} foram resetadas para o padrão.'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao resetar configurações: {str(e)}'}), 500

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