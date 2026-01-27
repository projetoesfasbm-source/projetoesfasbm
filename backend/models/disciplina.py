# backend/models/disciplina.py

from __future__ import annotations
import typing as t
from datetime import datetime, timezone
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship

if t.TYPE_CHECKING:
    from .historico_disciplina import HistoricoDisciplina
    from .disciplina_turma import DisciplinaTurma
    from .turma import Turma
    from .ciclo import Ciclo
    from .diario_classe import DiarioClasse
    from .horario import Horario

class Disciplina(db.Model):
    __tablename__ = 'disciplinas'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    materia: Mapped[str] = mapped_column(db.String(100))
    carga_horaria_prevista: Mapped[int] = mapped_column()
    carga_horaria_cumprida: Mapped[int] = mapped_column(default=0, server_default='0')
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    
    # --- RELAÇÃO ALTERADA: AGORA VINCULADA À TURMA ---
    turma_id: Mapped[int] = mapped_column(db.ForeignKey('turmas.id'), nullable=False)
    turma: Mapped["Turma"] = relationship(back_populates="disciplinas")
    
    ciclo_id: Mapped[int] = mapped_column(db.ForeignKey('ciclos.id'), nullable=False)
    ciclo: Mapped["Ciclo"] = relationship(back_populates="disciplinas")
    
    historico_disciplinas: Mapped[list["HistoricoDisciplina"]] = relationship(back_populates="disciplina", cascade="all, delete-orphan")
    associacoes_turmas: Mapped[list["DisciplinaTurma"]] = relationship(back_populates="disciplina", cascade="all, delete-orphan")
    
    # Relacionamento para exclusão em cascata dos diários associados
    diarios: Mapped[list["DiarioClasse"]] = relationship(back_populates="disciplina", cascade="all, delete-orphan")

    # Relacionamento para exclusão em cascata dos horários associados
    horarios: Mapped[list["Horario"]] = relationship(back_populates="disciplina", cascade="all, delete-orphan")
    
    # Adiciona uma constraint de unicidade para a matéria dentro de uma turma
    __table_args__ = (db.UniqueConstraint('materia', 'turma_id', name='_materia_turma_uc'),)

    def __init__(self, materia: str, carga_horaria_prevista: int, turma_id: int, ciclo_id: int, carga_horaria_cumprida: int = 0, **kw: t.Any) -> None:
        super().__init__(materia=materia, carga_horaria_prevista=carga_horaria_prevista, turma_id=turma_id, ciclo_id=ciclo_id, carga_horaria_cumprida=carga_horaria_cumprida, **kw)

    def __repr__(self):
        turma_nome = self.turma.nome if self.turma else 'N/A'
        return f"<Disciplina id={self.id} materia='{self.materia}' turma='{turma_nome}'>"