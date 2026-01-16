# backend/models/ciclo.py
from __future__ import annotations
import typing as t
from datetime import date
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Date

if t.TYPE_CHECKING:
    from .disciplina import Disciplina
    from .semana import Semana
    from .school import School

class Ciclo(db.Model):
    __tablename__ = 'ciclos'

    id: Mapped[int] = mapped_column(primary_key=True)
    # Removemos unique=True global para permitir nomes iguais em escolas diferentes
    nome: Mapped[str] = mapped_column(db.String(100), nullable=False)
    
    # --- DATAS PARA REGRA DE JUSTIÇA ---
    data_inicio: Mapped[t.Optional[date]] = mapped_column(Date, nullable=True)
    data_fim: Mapped[t.Optional[date]] = mapped_column(Date, nullable=True)
    # -----------------------------------

    # --- Vínculo com Escola ---
    school_id: Mapped[int] = mapped_column(db.ForeignKey('schools.id'), nullable=False, default=1)
    school: Mapped["School"] = relationship("School", backref="ciclos")

    # Relações
    disciplinas: Mapped[list["Disciplina"]] = relationship(back_populates="ciclo")
    semana: Mapped[list["Semana"]] = relationship(back_populates="ciclo") # Atenção: seu código original tinha 'semanas', mas verifique se é 'semana' ou 'semanas' no backref

    def __init__(self, nome: str, school_id: int = 1, data_inicio: date = None, data_fim: date = None, **kw: t.Any) -> None:
        super().__init__(nome=nome, school_id=school_id, data_inicio=data_inicio, data_fim=data_fim, **kw)

    def __repr__(self):
        return f"<Ciclo id={self.id} nome='{self.nome}' school_id={self.school_id}>"