# backend/models/horario.py
from __future__ import annotations
import typing as t
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship

if t.TYPE_CHECKING:
    from .disciplina import Disciplina
    from .instrutor import Instrutor
    from .semana import Semana

class Horario(db.Model):
    __tablename__ = 'horarios'

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # IMPORTANTE: Este sistema usa 'pelotao' (string) para ligar à Turma, não turma_id
    pelotao: Mapped[str] = mapped_column(db.String(50), nullable=False)
    
    dia_semana: Mapped[str] = mapped_column(db.String(20), nullable=False)
    periodo: Mapped[int] = mapped_column(nullable=False)
    duracao: Mapped[int] = mapped_column(default=1)

    observacao: Mapped[t.Optional[str]] = mapped_column(db.Text, nullable=True)

    semana_id: Mapped[int] = mapped_column(db.ForeignKey('semanas.id'), nullable=False)

    disciplina_id: Mapped[int] = mapped_column(db.ForeignKey('disciplinas.id'), nullable=False)
    instrutor_id: Mapped[int] = mapped_column(db.ForeignKey('instrutores.id'), nullable=False)
    
    instrutor_id_2: Mapped[t.Optional[int]] = mapped_column(db.ForeignKey('instrutores.id'), nullable=True)

    status: Mapped[str] = mapped_column(db.String(20), default='pendente', nullable=False)
    
    group_id: Mapped[t.Optional[str]] = mapped_column(db.String(36), nullable=True, index=True)

    # Relacionamentos
    semana: Mapped["Semana"] = relationship()
    
    # Atualizado para linkar com o cascade da Disciplina
    disciplina: Mapped["Disciplina"] = relationship(back_populates="horarios")
    
    instrutor: Mapped["Instrutor"] = relationship(foreign_keys=[instrutor_id])
    
    instrutor_2: Mapped[t.Optional["Instrutor"]] = relationship(foreign_keys=[instrutor_id_2])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<Horario id={self.id} pelotao='{self.pelotao}' semana_id={self.semana_id}>"

    # --- PROPRIEDADES VIRTUAIS PARA EVITAR ERRO NO TEMPLATE ---
    @property
    def hora_inicio(self):
        """Retorna horário fictício baseado no período para exibição."""
        # Ajuste estes horários conforme a realidade da escola
        horarios = {
            1: "07:45", 2: "08:35", 3: "09:40", 4: "10:30",
            5: "13:30", 6: "14:20", 7: "15:25", 8: "16:15"
        }
        return horarios.get(self.periodo, "--:--")

    @property
    def hora_fim(self):
        horarios = {
            1: "08:35", 2: "09:25", 3: "10:30", 4: "11:20",
            5: "14:20", 6: "15:10", 7: "16:15", 8: "17:05"
        }
        return horarios.get(self.periodo, "--:--")