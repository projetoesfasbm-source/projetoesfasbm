from __future__ import annotations
import typing as t
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship

if t.TYPE_CHECKING:
    from .turma import Turma
    from .aluno import Aluno

class TurmaCargo(db.Model):
    __tablename__ = 'turma_cargos'

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Nome do cargo (ex: "Chefe de Turma")
    cargo_nome: Mapped[str] = mapped_column(db.String(100), nullable=False)
    
    # Chaves estrangeiras
    turma_id: Mapped[int] = mapped_column(db.ForeignKey('turmas.id'), nullable=False)
    aluno_id: Mapped[t.Optional[int]] = mapped_column(db.ForeignKey('alunos.id'), nullable=True)

    # Relacionamentos
    turma: Mapped["Turma"] = relationship()
    aluno: Mapped[t.Optional["Aluno"]] = relationship()

    def __init__(self, turma_id: int, cargo_nome: str, aluno_id: t.Optional[int] = None, **kw: t.Any) -> None:
        super().__init__(turma_id=turma_id, cargo_nome=cargo_nome, aluno_id=aluno_id, **kw)

    def __repr__(self):
        return f"<TurmaCargo id={self.id} turma_id={self.turma_id} cargo='{self.cargo_nome}'>"