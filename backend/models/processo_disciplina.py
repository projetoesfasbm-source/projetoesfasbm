# backend/models/processo_disciplina.py
from __future__ import annotations
import typing as t
from datetime import datetime
from enum import Enum

from sqlalchemy import ForeignKey, String, Float, Text, Boolean, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .database import db

if t.TYPE_CHECKING:
    from .aluno import Aluno
    from .user import User
    from .discipline_rule import DisciplineRule

class StatusProcesso(str, Enum):
    AGUARDANDO_CIENCIA = "AGUARDANDO_CIENCIA"
    ALUNO_NOTIFICADO = "ALUNO_NOTIFICADO"
    DEFESA_ENVIADA = "DEFESA_ENVIADA"
    EM_ANALISE = "EM_ANALISE"
    FINALIZADO = "FINALIZADO"
    ARQUIVADO = "ARQUIVADO"

class ProcessoDisciplina(db.Model):
    __tablename__ = 'processos_disciplina'

    id: Mapped[int] = mapped_column(primary_key=True)
    
    aluno_id: Mapped[int] = mapped_column(ForeignKey('alunos.id'), nullable=False)
    relator_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    regra_id: Mapped[t.Optional[int]] = mapped_column(ForeignKey('discipline_rules.id'), nullable=True)

    codigo_infracao: Mapped[t.Optional[str]] = mapped_column(String(50), nullable=True)
    fato_constatado: Mapped[str] = mapped_column(Text, nullable=False)
    observacao: Mapped[t.Optional[str]] = mapped_column(Text, nullable=True)
    pontos: Mapped[float] = mapped_column(Float, default=0.0)
    
    status: Mapped[StatusProcesso] = mapped_column(
        String(50), 
        default=StatusProcesso.AGUARDANDO_CIENCIA,
        server_default=StatusProcesso.AGUARDANDO_CIENCIA.value
    )
    
    # DATAS (Atenção aqui: data_registro é nova)
    data_ocorrencia: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    data_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    data_ciente: Mapped[t.Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    data_defesa: Mapped[t.Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    data_decisao: Mapped[t.Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    defesa: Mapped[t.Optional[str]] = mapped_column(Text, nullable=True)
    decisao_final: Mapped[t.Optional[str]] = mapped_column(String(50), nullable=True)
    fundamentacao: Mapped[t.Optional[str]] = mapped_column(Text, nullable=True)
    detalhes_sancao: Mapped[t.Optional[str]] = mapped_column(Text, nullable=True)

    is_crime: Mapped[bool] = mapped_column(Boolean, default=False)
    tipo_sancao: Mapped[t.Optional[str]] = mapped_column(String(50), nullable=True)
    dias_sancao: Mapped[int] = mapped_column(Integer, default=0)
    origem_punicao: Mapped[str] = mapped_column(String(20), default='NPCCAL')
    ciente_aluno: Mapped[bool] = mapped_column(Boolean, default=False)

    # RELACIONAMENTOS CORRIGIDOS (Sem conflito)
    # Se 'Aluno' já tem 'processos_disciplinares', usamos ele aqui ou criamos um novo sem overlap.
    # Vou usar backref simples para evitar o erro de 'overlaps' se o Aluno não tiver nada definido explicitamente.
    # Se Aluno tiver definido, o backref será ignorado ou complementado.
    aluno = relationship("Aluno", backref="processos_novos") 
    
    relator: Mapped["User"] = relationship(foreign_keys=[relator_id])
    regra: Mapped[t.Optional["DisciplineRule"]] = relationship()

    def __repr__(self):
        return f"<Processo {self.id} - Aluno {self.aluno_id} - {self.status}>"