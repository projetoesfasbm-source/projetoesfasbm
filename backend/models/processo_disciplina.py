# backend/models/processo_disciplina.py

from __future__ import annotations
import typing as t
from datetime import datetime, timezone
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship

if t.TYPE_CHECKING:
    from .aluno import Aluno
    from .user import User

class ProcessoDisciplina(db.Model):
    __tablename__ = 'processos_disciplinares'

    id: Mapped[int] = mapped_column(primary_key=True)
    
    aluno_id: Mapped[int] = mapped_column(db.ForeignKey('alunos.id'), nullable=False)
    relator_id: Mapped[int] = mapped_column(db.ForeignKey('users.id'), nullable=False)

    fato_constatado: Mapped[str] = mapped_column(db.Text, nullable=False)
    observacao: Mapped[t.Optional[str]] = mapped_column(db.Text)
    status: Mapped[str] = mapped_column(db.String(50), default='Pendente', nullable=False)
    
    defesa: Mapped[t.Optional[str]] = mapped_column(db.Text)
    data_defesa: Mapped[t.Optional[datetime]] = mapped_column()
    
    decisao_final: Mapped[t.Optional[str]] = mapped_column(db.String(100))
    data_decisao: Mapped[t.Optional[datetime]] = mapped_column()
    
    # --- NOVO CAMPO ADICIONADO ---
    fundamentacao: Mapped[t.Optional[str]] = mapped_column(db.Text)

    data_ocorrencia: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    data_ciente: Mapped[t.Optional[datetime]] = mapped_column()

    aluno: Mapped["Aluno"] = relationship(back_populates="processos_disciplinares")
    relator: Mapped["User"] = relationship()

    def __repr__(self):
        return f"<ProcessoDisciplina id={self.id} aluno_id={self.aluno_id} status='{self.status}'>"