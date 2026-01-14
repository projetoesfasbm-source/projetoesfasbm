from __future__ import annotations
import typing as t
from datetime import date, datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Integer, Text, Float, DateTime, func
from .database import db

if t.TYPE_CHECKING:
    from .aluno import Aluno
    from .user import User

class Elogio(db.Model):
    __tablename__ = 'elogios'

    id: Mapped[int] = mapped_column(primary_key=True)
    aluno_id: Mapped[int] = mapped_column(ForeignKey('alunos.id'), nullable=False, index=True)
    registrado_por_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    data_elogio: Mapped[date] = mapped_column(db.Date, nullable=False)
    data_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Pontuação: 0.5 para CBFPM/CSPM, 0.0 para CTSP
    pontos: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # IDs dos atributos FADA (1 a 18) impactados
    atributo_1: Mapped[t.Optional[int]] = mapped_column(Integer, nullable=True)
    atributo_2: Mapped[t.Optional[int]] = mapped_column(Integer, nullable=True)

    # Relações
    aluno: Mapped['Aluno'] = relationship("Aluno", back_populates='elogios')
    registrador: Mapped['User'] = relationship("User", foreign_keys=[registrado_por_id])

    def __repr__(self):
        return f"<Elogio id={self.id} aluno={self.aluno_id} pts={self.pontos}>"