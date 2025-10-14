from __future__ import annotations
import typing as t
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship

if t.TYPE_CHECKING:
    from .disciplina import Disciplina
    from .instrutor import Instrutor

class DisciplinaTurma(db.Model):
    __tablename__ = 'disciplina_turmas'

    id: Mapped[int] = mapped_column(primary_key=True)
    
    pelotao: Mapped[str] = mapped_column(db.String(50), nullable=False)
    
    disciplina_id: Mapped[int] = mapped_column(db.ForeignKey('disciplinas.id'), nullable=False)
    
    instrutor_id_1: Mapped[t.Optional[int]] = mapped_column(db.ForeignKey('instrutores.id'), nullable=True)
    instrutor_id_2: Mapped[t.Optional[int]] = mapped_column(db.ForeignKey('instrutores.id'), nullable=True)

    disciplina: Mapped["Disciplina"] = relationship(back_populates="associacoes_turmas")
    instrutor_1: Mapped[t.Optional["Instrutor"]] = relationship(foreign_keys=[instrutor_id_1])
    instrutor_2: Mapped[t.Optional["Instrutor"]] = relationship(foreign_keys=[instrutor_id_2])

    def __init__(self, pelotao: str, disciplina_id: int, instrutor_id_1: t.Optional[int] = None, instrutor_id_2: t.Optional[int] = None, **kw: t.Any) -> None:
        super().__init__(pelotao=pelotao, disciplina_id=disciplina_id, instrutor_id_1=instrutor_id_1, instrutor_id_2=instrutor_id_2, **kw)

    def __repr__(self):
        return f"<DisciplinaTurma id={self.id} pelotao='{self.pelotao}' disciplina_id={self.disciplina_id}>"