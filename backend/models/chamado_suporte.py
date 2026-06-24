from __future__ import annotations
import typing as t
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, DateTime, String, Text
from datetime import datetime
from .database import db

if t.TYPE_CHECKING:
    from .user import User
    from .school import School

class ChamadoSuporte(db.Model):
    __tablename__ = 'chamados_suporte'

    id: Mapped[int] = mapped_column(primary_key=True)
    solicitante_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    escola_id: Mapped[t.Optional[int]] = mapped_column(ForeignKey('schools.id'), nullable=True)
    
    qso_contato: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo_login: Mapped[str] = mapped_column(String(50), nullable=False)
    matricula_problema: Mapped[t.Optional[str]] = mapped_column(String(50), nullable=True)
    tipo_problema: Mapped[str] = mapped_column(String(255), nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    
    anexo_filename: Mapped[t.Optional[str]] = mapped_column(String(255), nullable=True)
    
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='Aberto')
    
    data_criacao: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    data_conclusao: Mapped[t.Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relacionamentos
    solicitante: Mapped['User'] = relationship('User')
    escola: Mapped[t.Optional['School']] = relationship('School')

    def __repr__(self):
        return f'<ChamadoSuporte {self.id} - {self.status}>'
