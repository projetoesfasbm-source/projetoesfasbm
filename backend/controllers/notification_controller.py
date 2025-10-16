# backend/controllers/notification_controller.py
from flask import Blueprint, render_template, jsonify, redirect, url_for, request
from flask_login import login_required, current_user
from ..services.notification_service import NotificationService
from ..models.database import db

notification_bp = Blueprint('notification', __name__, url_prefix='/notifications')

@notification_bp.route('/')
@login_required
def index():
    """Página que exibe todas as notificações do usuário."""
    page = request.args.get('page', 1, type=int)
    notifications = NotificationService.get_all_notifications(current_user.id, page=page)
    return render_template('notifications/index.html', notifications=notifications)

@notification_bp.route('/api/unread')
@login_required
def get_unread():
    """Endpoint da API para buscar notificações não lidas."""
    notifications = NotificationService.get_unread_notifications(current_user.id)
    count = len(notifications)
    
    return jsonify({
        'count': count,
        'notifications': [{
            'id': n.id,
            'message': n.message,
            'url': n.url or '#',
            'created_at': n.created_at.strftime('%d/%m/%Y %H:%M')
        } for n in notifications]
    })

@notification_bp.route('/mark-as-read/<int:notification_id>', methods=['POST'])
@login_required
def mark_as_read(notification_id):
    """Endpoint da API para marcar uma notificação como lida."""
    success = NotificationService.mark_as_read(notification_id, current_user.id)
    if success:
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False}), 404