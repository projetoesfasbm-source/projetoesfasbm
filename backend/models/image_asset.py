# backend/models/image_asset.py

from __future__ import annotations
import typing as t
from datetime import datetime, timezone # <-- Importar timezone
from .database import db
from sqlalchemy.orm import Mapped, mapped_column

class ImageAsset(db.Model):
    __tablename__ = 'image_assets'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(db.String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(db.String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(db.String(50), nullable=False)
    category: Mapped[str] = mapped_column(db.String(50), nullable=False)
    description: Mapped[t.Optional[str]] = mapped_column(db.String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc)) # <-- CORRIGIDO
    uploaded_by: Mapped[int] = mapped_column(db.ForeignKey('users.id'))

    def __init__(self, filename: str, original_filename: str, asset_type: str, 
                 category: str, uploaded_by: int, description: t.Optional[str] = None, **kw: t.Any) -> None:
        super().__init__(filename=filename, original_filename=original_filename, 
                         asset_type=asset_type, category=category, uploaded_by=uploaded_by,
                         description=description, **kw)

    def __repr__(self):
        return f"<ImageAsset id={self.id} filename='{self.filename}' type='{self.asset_type}'>"