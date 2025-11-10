# backend/models/avaliacao.py
from __future__ import annotations
import typing as t
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Integer, Float, String, Text, DateTime
from sqlalchemy.sql import func
from .database import db

if t.TYPE_CHECKING:
    from .aluno import Aluno
    from .user import User

class AvaliacaoAtitudinal(db.Model):
    """
    Representa a Ficha de Avaliação Atitudinal (AAt).
    """
    __tablename__ = 'avaliacoes_atitudinais'

    id: Mapped[int] = mapped_column(primary_key=True)
    aluno_id: Mapped[int] = mapped_column(ForeignKey('alunos.id'), nullable=False, index=True)
    avaliador_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    data_fechamento: Mapped[t.Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Período que esta avaliação compreende (ex: 1º Trimestre)
    periodo_inicio: Mapped[t.Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    periodo_fim: Mapped[t.Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default='rascunho', nullable=False) # 'rascunho' ou 'finalizada'

    # Notas
    nota_disciplinar: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)
    nota_fada: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    nota_final: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    observacoes: Mapped[t.Optional[str]] = mapped_column(Text, nullable=True)

    # Relacionamentos
    aluno: Mapped['Aluno'] = relationship(back_populates='avaliacoes')
    avaliador: Mapped['User'] = relationship(foreign_keys=[avaliador_id])
    itens: Mapped[list['AvaliacaoItem']] = relationship(back_populates='avaliacao', cascade="all, delete-orphan")

class AvaliacaoItem(db.Model):
    """
    Itens da FADA (parte subjetiva).
    """
    __tablename__ = 'avaliacao_itens'

    id: Mapped[int] = mapped_column(primary_key=True)
    avaliacao_id: Mapped[int] = mapped_column(ForeignKey('avaliacoes_atitudinais.id'), nullable=False, index=True)
    
    criterio: Mapped[str] = mapped_column(String(100), nullable=False)
    nota: Mapped[float] = mapped_column(Float, nullable=False)

    avaliacao: Mapped['AvaliacaoAtitudinal'] = relationship(back_populates='itens')