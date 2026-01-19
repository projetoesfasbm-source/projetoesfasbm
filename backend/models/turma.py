# backend/models/turma.py
from __future__ import annotations
import typing as t
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Date
from enum import Enum

if t.TYPE_CHECKING:
    from .aluno import Aluno
    from .school import School
    from .disciplina import Disciplina 

class TurmaStatus(str, Enum):
    # Novos status
    EM_ANDAMENTO = "EM_ANDAMENTO"
    CONCLUIDA = "CONCLUIDA"
    
    # Status Legados (Mantidos para compatibilidade)
    ATIVA = "ativa"
    CANCELADA = "cancelada"
    CONCLUIDA_OLD = "concluida" 

class Turma(db.Model):
    __tablename__ = 'turmas'

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # ALTERAÇÃO: Removido unique=True global. A unicidade agora é composta (ver __table_args__)
    nome: Mapped[str] = mapped_column(db.String(100), nullable=False)
    
    ano: Mapped[str] = mapped_column(db.String(20), nullable=False)
    
    school_id: Mapped[int] = mapped_column(db.ForeignKey('schools.id'), nullable=False)

    data_formatura: Mapped[t.Optional[Date]] = mapped_column(Date, nullable=True)

    status: Mapped[TurmaStatus] = mapped_column(
        db.String(30), 
        default=TurmaStatus.EM_ANDAMENTO, 
        server_default=TurmaStatus.EM_ANDAMENTO, 
        nullable=False
    )

    # Relações
    alunos: Mapped[list["Aluno"]] = relationship(back_populates="turma")
    school: Mapped["School"] = relationship(back_populates="turmas")
    disciplinas: Mapped[list["Disciplina"]] = relationship(back_populates="turma", cascade="all, delete-orphan")
    cargos: Mapped[list["TurmaCargo"]] = relationship(back_populates="turma", cascade="all, delete-orphan")

    # NOVA REGRA: O nome deve ser único APENAS dentro da mesma escola
    __table_args__ = (
        db.UniqueConstraint('nome', 'school_id', name='uq_turma_nome_escola'),
    )

    def __init__(self, nome: str, ano: str, **kw: t.Any) -> None:
        super().__init__(nome=nome, ano=ano, **kw)

    def __repr__(self):
        return f"<Turma id={self.id} nome='{self.nome}'>"