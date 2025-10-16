# backend/services/notification_service.py
from sqlalchemy import select
from ..models.database import db
from ..models.notification import Notification
from ..models.user import User
from ..models.user_school import UserSchool

class NotificationService:
    @staticmethod
    def create_notification(user_id: int, message: str, url: str = None):
        """Cria uma única notificação para um usuário."""
        if not user_id:
            return
        notification = Notification(user_id=user_id, message=message, url=url)
        db.session.add(notification)

    @staticmethod
    def create_notification_for_roles(school_id: int, roles: list[str], message: str, url: str = None):
        """Cria notificações para todos os usuários com certas funções em uma escola."""
        if not school_id or not roles:
            return

        user_ids_query = (
            select(User.id)
            .join(UserSchool)
            .where(
                UserSchool.school_id == school_id,
                UserSchool.role.in_(roles)
            )
        )
        user_ids = db.session.scalars(user_ids_query).all()

        for user_id in user_ids:
            NotificationService.create_notification(user_id, message, url)

    @staticmethod
    def get_unread_notifications(user_id: int, limit: int = 5):
        """Busca as notificações não lidas de um usuário."""
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        return db.session.scalars(stmt).all()

    @staticmethod
    def get_all_notifications(user_id: int, page: int = 1, per_page: int = 20):
        """Busca todas as notificações de um usuário de forma paginada."""
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
        )
        return db.paginate(stmt, page=page, per_page=per_page, error_out=False)


    @staticmethod
    def mark_as_read(notification_id: int, user_id: int):
        """Marca uma notificação específica como lida, verificando a propriedade."""
        notification = db.session.get(Notification, notification_id)
        if notification and notification.user_id == user_id:
            notification.is_read = True
            return True
        return False