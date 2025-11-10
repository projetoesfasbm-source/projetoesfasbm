# backend/models/avaliacao.py
from __future__ import annotations
import typing as t
from datetime import datetime
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
    Exclusivo para cursos CBFPM e CSPM.
    """
    __tablename__ = 'avaliacoes_atitudinais'

    id: Mapped[int] = mapped_column(primary_key=True)
    aluno_id: Mapped[int] = mapped_column(ForeignKey('alunos.id'), nullable=False, index=True)
    avaliador_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    
    # Timestamps com timezone para maior precisão
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    data_fechamento: Mapped[t.Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Período é obrigatório pois define quais punições entram no cálculo
    periodo_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    periodo_fim: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Status: 'rascunho' permite salvar sem finalizar o cálculo
    status: Mapped[str] = mapped_column(String(20), default='rascunho', nullable=False)

    # Notas (0.0 a 10.0)
    nota_disciplinar: Mapped[float] = mapped_column(Float, default=10.0, nullable=False) # Começa com 10 até ter punições
    nota_fada: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)        # Média subjetiva
    nota_final: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)       # (NDisc + FADA) / 2

    observacoes: Mapped[t.Optional[str]] = mapped_column(Text, nullable=True)

    # Relacionamentos
    aluno: Mapped['Aluno'] = relationship(back_populates='avaliacoes')
    avaliador: Mapped['User'] = relationship(foreign_keys=[avaliador_id])
    itens: Mapped[list['AvaliacaoItem']] = relationship(back_populates='avaliacao', cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<AvaliacaoAtitudinal id={self.id} aluno_id={self.aluno_id} status='{self.status}'>"

class AvaliacaoItem(db.Model):
    """
    Itens individuais da FADA (parte subjetiva).
    Armazena a nota de cada critério (ex: "Apresentação Pessoal": 9.5).
    """
    __tablename__ = 'avaliacao_itens'

    id: Mapped[int] = mapped_column(primary_key=True)
    avaliacao_id: Mapped[int] = mapped_column(ForeignKey('avaliacoes_atitudinais.id'), nullable=False, index=True)
    
    criterio: Mapped[str] = mapped_column(String(100), nullable=False)
    nota: Mapped[float] = mapped_column(Float, nullable=False)

    avaliacao: Mapped['AvaliacaoAtitudinal'] = relationship(back_populates='itens')

    def __repr__(self) -> str:
        return f"<AvaliacaoItem {self.criterio}: {self.nota}>"