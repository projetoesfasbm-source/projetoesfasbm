from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from backend.services.log_service import LogService

# Criamos o blueprint (o roteador) para os logs
log_bp = Blueprint('log_controller', __name__)

@log_bp.route('/logs', methods=['GET'])
@login_required
def render_logs_page():
    """Rota para renderizar a página HTML principal dos Logs"""
    # Verificação de segurança: Apenas super_admin ou admin podem ver
    if current_user.role not in ['super_admin', 'admin']: 
         return "Acesso Negado", 403
    return render_template('logs_auditoria.html')

@log_bp.route('/api/logs', methods=['GET'])
@login_required
def api_buscar_logs():
    """API para buscar os logs e retorná-los em formato JSON para a tela"""
    # Verificação de segurança adicional
    if current_user.role not in ['super_admin', 'admin']: 
         return jsonify({'status': 'error', 'message': 'Acesso Negado'}), 403

    try:
        data_inicio = request.args.get('dataInicio')
        data_fim = request.args.get('dataFim')
        usuario_id = request.args.get('usuarioId')

        if usuario_id and usuario_id.isdigit():
            usuario_id = int(usuario_id)
        else:
            usuario_id = None

        # Chama o serviço seguro que você já tinha pronto
        logs = LogService.get_logs(
            school_id=current_user.temp_active_school_id or current_user.school_id, 
            date_start=data_inicio, 
            date_end=data_fim, 
            user_id=usuario_id,
            limit=100 
        )

        resultado = []
        for log in logs:
            # Pega o nome do usuário de forma segura
            user_name = "Sistema"
            if log.user:
                # Tenta pegar 'nome', se não achar tenta 'username'
                user_name = getattr(log.user, 'nome', getattr(log.user, 'username', 'Usuário Desconhecido'))

            resultado.append({
                'id': log.id,
                'data_hora': log.timestamp.strftime('%d/%m/%Y %H:%M:%S') if log.timestamp else 'N/A',
                'usuario': user_name,
                'acao': log.action,
                'detalhes': log.details or '-'
            })

        return jsonify({'status': 'success', 'logs': resultado})

    except Exception as e:
        print(f"ERRO AO BUSCAR LOGS: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
