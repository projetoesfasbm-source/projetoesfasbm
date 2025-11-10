# backend/models/school.py

from __future__ import annotations
import typing as t
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import db

if t.TYPE_CHECKING:
    from .user import User
    from .user_school import UserSchool
    from .turma import Turma
    # A importação de Disciplina não é mais necessária aqui

class School(db.Model):
    __tablename__ = 'schools'

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(db.String(150), nullable=False)
    slug: Mapped[t.Optional[str]] = mapped_column(db.String(150), nullable=True, unique=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        onupdate=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    # --- NOVO CAMPO ADICIONADO ---
    # Define qual regulamento (NPCCAL) esta escola segue: 'cfs', 'cbfpm', 'cspm'
    # O 'default' e 'server_default' garantem que escolas existentes funcionem
    npccal_type: Mapped[str] = mapped_column(db.String(20), nullable=False, default='cfs', server_default='cfs')
    # -------------------------------

    user_schools: Mapped[list['UserSchool']] = relationship('UserSchool', back_populates='school', cascade="all, delete-orphan")

    @property
    def users(self) -> list['User']:
        return [us.user for us in self.user_schools]

    turmas: Mapped[list['Turma']] = relationship('Turma', back_populates='school', cascade="all, delete-orphan")
    
    # --- RELAÇÃO REMOVIDA (Mantido seu comentário) ---
    # disciplinas: Mapped[list['Disciplina']] = relationship('Disciplina', back_populates='school', cascade="all, delete-orphan")

    __table_args__ = (
        db.UniqueConstraint('nome', name='uq_school_nome'),
    )

    def __repr__(self) -> str:
        return f"<School id={self.id} nome='{self.nome}'>"