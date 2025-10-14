from __future__ import annotations
import typing as t
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship

class Resposta(db.Model):
    __tablename__ = 'respostas'

    id: Mapped[int] = mapped_column(primary_key=True)
    
    questionario_id: Mapped[int] = mapped_column(db.ForeignKey('questionarios.id'), nullable=False)
    pergunta_id: Mapped[int] = mapped_column(db.ForeignKey('perguntas.id'), nullable=False)
    opcao_resposta_id: Mapped[t.Optional[int]] = mapped_column(db.ForeignKey('opcoes_respostas.id'), nullable=True)
    texto_livre: Mapped[t.Optional[str]] = mapped_column(db.String(500), nullable=True)
    
    user_id: Mapped[int] = mapped_column(db.ForeignKey('users.id'), nullable=False)

    def __init__(self, questionario_id: int, pergunta_id: int, user_id: int, 
                 opcao_resposta_id: t.Optional[int] = None, texto_livre: t.Optional[str] = None, **kw: t.Any) -> None:
        super().__init__(questionario_id=questionario_id, pergunta_id=pergunta_id, user_id=user_id,
                         opcao_resposta_id=opcao_resposta_id, texto_livre=texto_livre, **kw)

    def __repr__(self):
        return f"<Resposta id={self.id}>"