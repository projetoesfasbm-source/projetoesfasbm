# backend/controllers/push_controller.py
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from ..models.database import db
from ..models.push_subscription import PushSubscription

push_bp = Blueprint('push', __name__, url_prefix='/push')

@push_bp.route('/register-device', methods=['POST'])
@login_required
def register_device():
    """
    Endpoint para o aplicativo móvel registrar ou atualizar o token FCM 
    de um dispositivo para o usuário logado.
    """
    data = request.get_json()
    token = data.get('token')

    if not token:
        return jsonify({'success': False, 'message': 'Token não fornecido.'}), 400

    # Verifica se o token já existe para evitar duplicatas
    existing_sub = db.session.query(PushSubscription).filter_by(fcm_token=token).first()
    
    if existing_sub:
        # Se o token já existe, apenas garante que está associado ao usuário correto
        if existing_sub.user_id != current_user.id:
            existing_sub.user_id = current_user.id
            db.session.commit()
        return jsonify({'success': True, 'message': 'Token do dispositivo já registrado.'}), 200

    # Se não existe, cria uma nova inscrição
    new_sub = PushSubscription(
        user_id=current_user.id,
        fcm_token=token
    )
    db.session.add(new_sub)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Dispositivo registrado para notificações.'}), 201