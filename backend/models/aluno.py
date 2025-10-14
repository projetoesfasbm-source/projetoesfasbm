# backend/models/aluno.py
from __future__ import annotations
import typing as t
from datetime import date
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship

if t.TYPE_CHECKING:
    from .user import User
    from .historico import HistoricoAluno
    from .historico_disciplina import HistoricoDisciplina
    from .turma import Turma
    from .processo_disciplina import ProcessoDisciplina # <-- NOVA IMPORTAÇÃO

class Aluno(db.Model):
    __tablename__ = 'alunos'

    id: Mapped[int] = mapped_column(primary_key=True)
    id_aluno: Mapped[str] = mapped_column(db.String(20), unique=True, nullable=True)
    opm: Mapped[str] = mapped_column(db.String(50))
    num_aluno: Mapped[str] = mapped_column(db.String(20), nullable=True)
    funcao_atual: Mapped[t.Optional[str]] = mapped_column(db.String(50))
    foto_perfil: Mapped[str] = mapped_column(db.String(255), default='default.png')
    
    telefone: Mapped[t.Optional[str]] = mapped_column(db.String(20))
    
    data_nascimento: Mapped[t.Optional[date]] = mapped_column(db.Date)
    
    turma_id: Mapped[t.Optional[int]] = mapped_column(db.ForeignKey('turmas.id'))
    turma: Mapped[t.Optional["Turma"]] = relationship(back_populates="alunos")

    user_id: Mapped[int] = mapped_column(db.ForeignKey('users.id'), unique=True)
    user: Mapped["User"] = relationship(back_populates="aluno_profile")

    historico: Mapped[list["HistoricoAluno"]] = relationship(back_populates="aluno", cascade="all, delete-orphan")
    historico_disciplinas: Mapped[list["HistoricoDisciplina"]] = relationship(back_populates="aluno", cascade="all, delete-orphan")

    # --- NOVA RELAÇÃO ADICIONADA ---
    processos_disciplinares: Mapped[list["ProcessoDisciplina"]] = relationship(back_populates="aluno", cascade="all, delete-orphan")

    def __init__(self, user_id: int, opm: str, 
                 id_aluno: t.Optional[str] = None, num_aluno: t.Optional[str] = None,
                 funcao_atual: t.Optional[str] = None, foto_perfil: str = 'default.png',
                 telefone: t.Optional[str] = None, data_nascimento: t.Optional[date] = None, 
                 turma_id: t.Optional[int] = None, **kw: t.Any) -> None:
        super().__init__(user_id=user_id, opm=opm,
                         id_aluno=id_aluno, num_aluno=num_aluno,
                         funcao_atual=funcao_atual, foto_perfil=foto_perfil,
                         telefone=telefone, data_nascimento=data_nascimento, turma_id=turma_id, **kw)

    def __repr__(self):
        matricula_repr = self.user.matricula if self.user else 'N/A'
        return f"<Aluno id={self.id} matricula='{matricula_repr}'>"