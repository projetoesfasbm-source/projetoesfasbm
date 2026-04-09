from __future__ import annotations
import typing as t
from datetime import datetime, timezone
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship

if t.TYPE_CHECKING:
    from .user import User

class SiteConfig(db.Model):
    __tablename__ = 'site_configs'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    config_key: Mapped[str] = mapped_column(db.String(100), unique=True, nullable=False)
    config_value: Mapped[t.Optional[str]] = mapped_column(db.String(500))
    config_type: Mapped[str] = mapped_column(db.String(50), default='text')  # 'text', 'image', 'color'
    description: Mapped[t.Optional[str]] = mapped_column(db.String(255))
    category: Mapped[str] = mapped_column(db.String(50), default='general')  # 'general', 'dashboard', 'sidebar'
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    updated_by: Mapped[t.Optional[int]] = mapped_column(db.ForeignKey('users.id'))

    # Relacionamento
    updated_by_user: Mapped[t.Optional['User']] = relationship(back_populates='site_configs_updated')

    def __init__(self, config_key: str, config_value: t.Optional[str] = None, 
                 config_type: str = 'text', description: t.Optional[str] = None,
                 category: str = 'general', updated_by: t.Optional[int] = None, **kw: t.Any) -> None:
        super().__init__(config_key=config_key, config_value=config_value, 
                         config_type=config_type, description=description,
                         category=category, updated_by=updated_by, **kw)

    def __repr__(self):
        return f"<SiteConfig key='{self.config_key}' value='{self.config_value}'>"