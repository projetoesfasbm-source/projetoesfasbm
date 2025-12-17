# backend/models/frequencia.py
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey
import typing as t

if t.TYPE_CHECKING:
    from .diario_classe import DiarioClasse
    from .aluno import Aluno

class FrequenciaAluno(db.Model):
    __tablename__ = 'frequencias_alunos'

    id: Mapped[int] = mapped_column(primary_key=True)
    diario_id: Mapped[int] = mapped_column(ForeignKey('diarios_classe.id'), nullable=False)
    aluno_id: Mapped[int] = mapped_column(ForeignKey('alunos.id'), nullable=False)
    
    # True = Presente, False = Falta
    presente: Mapped[bool] = mapped_column(db.Boolean, default=True)
    justificativa: Mapped[t.Optional[str]] = mapped_column(db.String(255)) 

    diario: Mapped["DiarioClasse"] = relationship(back_populates="frequencias")
    aluno: Mapped["Aluno"] = relationship(back_populates="frequencias")