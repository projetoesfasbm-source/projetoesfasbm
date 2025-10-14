# backend/models/semana.py
from __future__ import annotations
import typing as t
from datetime import date
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship

if t.TYPE_CHECKING:
    from .ciclo import Ciclo # Importa o novo modelo

class Semana(db.Model):
    __tablename__ = 'semanas'

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(db.String(100), nullable=False)
    data_inicio: Mapped[date] = mapped_column(db.Date, nullable=False)
    data_fim: Mapped[date] = mapped_column(db.Date, nullable=False)

    # ALTERAÇÃO: Substituído o campo de inteiro por uma relação
    ciclo_id: Mapped[int] = mapped_column(db.ForeignKey('ciclos.id'), nullable=False)
    ciclo: Mapped["Ciclo"] = relationship(back_populates="semanas")

    mostrar_periodo_13: Mapped[bool] = mapped_column(default=False, server_default='0')
    mostrar_periodo_14: Mapped[bool] = mapped_column(default=False, server_default='0')
    mostrar_periodo_15: Mapped[bool] = mapped_column(default=False, server_default='0')
    
    mostrar_sabado: Mapped[bool] = mapped_column(default=False, server_default='0')
    periodos_sabado: Mapped[int] = mapped_column(default=0, server_default='0')
    mostrar_domingo: Mapped[bool] = mapped_column(default=False, server_default='0')
    periodos_domingo: Mapped[int] = mapped_column(default=0, server_default='0')

    def __init__(self, nome: str, data_inicio: date, data_fim: date, ciclo_id: int, **kw: t.Any) -> None:
        super().__init__(nome=nome, data_inicio=data_inicio, data_fim=data_fim, ciclo_id=ciclo_id, **kw)

    def __repr__(self):
        return f"<Semana id={self.id} nome='{self.nome}'>"