from __future__ import annotations
import typing as t
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship

if t.TYPE_CHECKING:
    from .pergunta import Pergunta

class OpcaoResposta(db.Model):
    __tablename__ = 'opcoes_respostas'

    id: Mapped[int] = mapped_column(primary_key=True)
    texto: Mapped[str] = mapped_column(db.String(200), nullable=False)
    
    pergunta_id: Mapped[int] = mapped_column(db.ForeignKey('perguntas.id'), nullable=False)
    pergunta: Mapped[Pergunta] = relationship(back_populates="opcoes")

    def __init__(self, texto: str, pergunta_id: int, **kw: t.Any) -> None:
        super().__init__(texto=texto, pergunta_id=pergunta_id, **kw)

    def __repr__(self):
        return f"<OpcaoResposta id={self.id} texto='{self.texto}'>"