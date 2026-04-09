from __future__ import annotations
import typing as t
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship

if t.TYPE_CHECKING:
    from .questionario import Questionario
    from .opcao_resposta import OpcaoResposta

class Pergunta(db.Model):
    __tablename__ = 'perguntas'

    id: Mapped[int] = mapped_column(primary_key=True)
    texto: Mapped[str] = mapped_column(db.String(500), nullable=False)
    
    # --- LINHA ADICIONADA ---
    # Define se a pergunta é de resposta 'unica' ou 'multipla'
    tipo: Mapped[str] = mapped_column(db.String(20), nullable=False, default='unica')
    
    questionario_id: Mapped[int] = mapped_column(db.ForeignKey('questionarios.id'), nullable=False)
    questionario: Mapped[Questionario] = relationship(back_populates="perguntas")
    
    opcoes: Mapped[list[OpcaoResposta]] = relationship(back_populates="pergunta", cascade="all, delete-orphan")

    def __init__(self, texto: str, questionario_id: int, tipo: str = 'unica', **kw: t.Any) -> None:
        super().__init__(texto=texto, questionario_id=questionario_id, tipo=tipo, **kw)

    def __repr__(self):
        return f"<Pergunta id={self.id} texto='{self.texto}'>"