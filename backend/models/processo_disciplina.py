from __future__ import annotations
import typing as t
import enum
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String, Text, DateTime, Enum, Float, Index
from sqlalchemy.sql import func
from .database import db

if t.TYPE_CHECKING:
    from .aluno import Aluno
    from .user import User
    from .discipline_rule import DisciplineRule

class StatusProcesso(str, enum.Enum):
    AGUARDANDO_CIENCIA = 'Aguardando Ciência'
    ALUNO_NOTIFICADO = 'Aluno Notificado'
    DEFESA_ENVIADA = 'Defesa Enviada'
    FINALIZADO = 'Finalizado'

class ProcessoDisciplina(db.Model):
    __tablename__ = 'processos_disciplina'

    id: Mapped[int] = mapped_column(primary_key=True)
    aluno_id: Mapped[int] = mapped_column(ForeignKey('alunos.id'), nullable=False, index=True)
    relator_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)

    # --- Integridade e Rastreabilidade ---
    regra_id: Mapped[t.Optional[int]] = mapped_column(ForeignKey('discipline_rules.id'), nullable=True, index=True)
    codigo_infracao: Mapped[t.Optional[str]] = mapped_column(String(50), nullable=True) 
    
    fato_constatado: Mapped[str] = mapped_column(Text, nullable=False)
    observacao: Mapped[t.Optional[str]] = mapped_column(Text, nullable=True)
    
    pontos: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Uso de Enum com native_enum=False para garantir compatibilidade entre bancos (salva como String)
    status: Mapped[StatusProcesso] = mapped_column(
        Enum(StatusProcesso, name='status_processo_disciplinar', native_enum=False),
        default=StatusProcesso.AGUARDANDO_CIENCIA,
        nullable=False,
        index=True
    )
    
    # Timestamps com Timezone explícito
    data_ocorrencia: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    data_ciente: Mapped[t.Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    data_defesa: Mapped[t.Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    data_decisao: Mapped[t.Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Defesa e Decisão
    defesa: Mapped[t.Optional[str]] = mapped_column(Text, nullable=True)
    decisao_final: Mapped[t.Optional[str]] = mapped_column(String(50), nullable=True)
    fundamentacao: Mapped[t.Optional[str]] = mapped_column(Text, nullable=True)
    detalhes_sancao: Mapped[t.Optional[str]] = mapped_column(Text, nullable=True)
    ciente_aluno: Mapped[bool] = mapped_column(default=False)

    # Relacionamentos
    aluno: Mapped['Aluno'] = relationship(back_populates='processos_disciplinares')
    relator: Mapped['User'] = relationship(foreign_keys=[relator_id])
    regra: Mapped['DisciplineRule'] = relationship(foreign_keys=[regra_id])

    # Índices Compostos para Performance de Dashboards
    __table_args__ = (
        Index('idx_processo_status_data', 'status', 'data_ocorrencia'),
        Index('idx_processo_codigo', 'codigo_infracao'),
    )

    def __repr__(self) -> str:
        return f"<ProcessoDisciplina id={self.id} aluno={self.aluno_id} status='{self.status.value}'>"