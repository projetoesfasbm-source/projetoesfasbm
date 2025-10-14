# backend/models/ciclo.py
from __future__ import annotations
import typing as t
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship

if t.TYPE_CHECKING:
    from .disciplina import Disciplina
    from .semana import Semana

class Ciclo(db.Model):
    __tablename__ = 'ciclos'

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(db.String(100), unique=True, nullable=False)
    
    # Relações: Um ciclo pode ter várias disciplinas e semanas
    disciplinas: Mapped[list["Disciplina"]] = relationship(back_populates="ciclo")
    semanas: Mapped[list["Semana"]] = relationship(back_populates="ciclo")

    def __init__(self, nome: str, **kw: t.Any) -> None:
        super().__init__(nome=nome, **kw)

    def __repr__(self):
        return f"<Ciclo id={self.id} nome='{self.nome}'>"