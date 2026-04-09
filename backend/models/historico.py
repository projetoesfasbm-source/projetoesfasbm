# backend/models/historico.py

from __future__ import annotations
import typing as t
from datetime import datetime, timezone # <-- Importar timezone
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship

if t.TYPE_CHECKING:
    from .aluno import Aluno


class HistoricoAluno(db.Model):
    __tablename__ = 'historico_alunos'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(db.String(50))
    descricao: Mapped[str] = mapped_column(db.String(255))
    data_inicio: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc)) # <-- CORRIGIDO
    data_fim: Mapped[t.Optional[datetime]] = mapped_column(nullable=True)

    aluno_id: Mapped[int] = mapped_column(db.ForeignKey('alunos.id'))
    aluno: Mapped["Aluno"] = relationship(back_populates="historico")

    def __init__(self, aluno_id: int, tipo: str, descricao: str, 
                 data_inicio: t.Optional[datetime] = None, data_fim: t.Optional[datetime] = None, 
                 **kw: t.Any) -> None:
        super().__init__(aluno_id=aluno_id, tipo=tipo, descricao=descricao, 
                         data_inicio=data_inicio if data_inicio is not None else datetime.now(timezone.utc), # <-- CORRIGIDO
                         data_fim=data_fim, **kw)

    def __repr__(self):
        return f"<HistoricoAluno id={self.id} tipo='{self.tipo}' aluno_id={self.aluno_id}>"