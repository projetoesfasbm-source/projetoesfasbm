# backend/models/ciclo.py
from __future__ import annotations
import typing as t
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship

if t.TYPE_CHECKING:
    from .disciplina import Disciplina
    from .semana import Semana
    from .school import School

class Ciclo(db.Model):
    __tablename__ = 'ciclos'

    id: Mapped[int] = mapped_column(primary_key=True)
    # Removemos unique=True global para permitir nomes iguais em escolas diferentes
    nome: Mapped[str] = mapped_column(db.String(100), nullable=False)
    
    # --- Vínculo com Escola ---
    school_id: Mapped[int] = mapped_column(db.ForeignKey('schools.id'), nullable=False, default=1)
    school: Mapped["School"] = relationship("School", backref="ciclos")

    # Relações
    disciplinas: Mapped[list["Disciplina"]] = relationship(back_populates="ciclo")
    semanas: Mapped[list["Semana"]] = relationship(back_populates="ciclo")

    def __init__(self, nome: str, school_id: int = 1, **kw: t.Any) -> None:
        super().__init__(nome=nome, school_id=school_id, **kw)

    def __repr__(self):
        return f"<Ciclo id={self.id} nome='{self.nome}' school_id={self.school_id}>"