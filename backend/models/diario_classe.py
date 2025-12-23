# backend/models/diario_classe.py
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey
from datetime import date, datetime
import typing as t

if t.TYPE_CHECKING:
    from .turma import Turma
    from .disciplina import Disciplina
    from .user import User
    from .frequencia import FrequenciaAluno

class DiarioClasse(db.Model):
    __tablename__ = 'diarios_classe'

    id: Mapped[int] = mapped_column(primary_key=True)
    data_aula: Mapped[date] = mapped_column(db.Date, nullable=False)
    
    # ### ALTERAÇÃO AQUI ###
    # Adicionado campo para salvar o período exato (ex: 1, 2, 7, 8)
    periodo: Mapped[t.Optional[int]] = mapped_column(db.Integer, nullable=True)
    # ### FIM DA ALTERAÇÃO ###

    # Vínculos
    turma_id: Mapped[int] = mapped_column(ForeignKey('turmas.id'), nullable=False)
    disciplina_id: Mapped[int] = mapped_column(ForeignKey('disciplinas.id'), nullable=False)
    
    # Quem preencheu (O Chefe de Turma)
    responsavel_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    
    conteudo_ministrado: Mapped[t.Optional[str]] = mapped_column(db.Text)
    observacoes: Mapped[t.Optional[str]] = mapped_column(db.Text)
    
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=db.func.now())

    # Relacionamentos
    turma: Mapped["Turma"] = relationship()
    disciplina: Mapped["Disciplina"] = relationship()
    responsavel: Mapped["User"] = relationship()
    frequencias: Mapped[list["FrequenciaAluno"]] = relationship(back_populates="diario", cascade="all, delete-orphan")