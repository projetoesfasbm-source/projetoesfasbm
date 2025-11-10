# backend/models/processo_disciplina.py
from __future__ import annotations
import typing as t
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String, Text, DateTime, Enum, Float # <-- Adicionado Float
from sqlalchemy.sql import func
from datetime import datetime, timezone

if t.TYPE_CHECKING:
    from .aluno import Aluno
    from .user import User

class ProcessoDisciplina(db.Model):
    __tablename__ = 'processos_disciplina'

    id: Mapped[int] = mapped_column(primary_key=True)
    aluno_id: Mapped[int] = mapped_column(ForeignKey('alunos.id'), nullable=False, index=True)
    relator_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)

    fato_constatado: Mapped[str] = mapped_column(Text, nullable=False)
    observacao: Mapped[t.Optional[str]] = mapped_column(Text, nullable=True)
    
    # --- NOVO CAMPO ADICIONADO ---
    # Armazena a pontuação da regra no momento da criação.
    # Será 0.0 para CTSP e o valor real para CBFPM/CSPM.
    pontos: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # -----------------------------

    status: Mapped[str] = mapped_column(
        Enum('Aguardando Ciência', 'Aluno Notificado', 'Defesa Enviada', 'Finalizado', name='status_processo_disciplinar'),
        default='Aguardando Ciência',
        nullable=False
    )
    
    # Timestamps
    data_ocorrencia: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    data_ciente: Mapped[t.Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    data_defesa: Mapped[t.Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    data_decisao: Mapped[t.Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Defesa e Decisão
    defesa: Mapped[t.Optional[str]] = mapped_column(Text, nullable=True)
    decisao_final: Mapped[t.Optional[str]] = mapped_column(String(50), nullable=True)
    fundamentacao: Mapped[t.Optional[str]] = mapped_column(Text, nullable=True)
    detalhes_sancao: Mapped[t.Optional[str]] = mapped_column(Text, nullable=True) 

    # Relacionamentos
    aluno: Mapped['Aluno'] = relationship(back_populates='processos_disciplinares')
    relator: Mapped['User'] = relationship(foreign_keys=[relator_id])

    def __repr__(self) -> str:
        return f"<ProcessoDisciplina id={self.id} aluno_id={self.aluno_id} status='{self.status}'>"