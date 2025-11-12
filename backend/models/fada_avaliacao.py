# backend/models/fada_avaliacao.py

from __future__ import annotations
import typing as t
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Integer, String, Text, DateTime, Float, func
from .database import db

if t.TYPE_CHECKING:
    from .aluno import Aluno
    from .user import User

class FadaAvaliacao(db.Model):
    __tablename__ = 'fada_avaliacao'

    id: Mapped[int] = mapped_column(primary_key=True)
    aluno_id: Mapped[int] = mapped_column(ForeignKey('alunos.id'), nullable=False)
    avaliador_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    
    data_avaliacao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        default=lambda: datetime.now(timezone.utc)
    )

    # Relações
    aluno: Mapped['Aluno'] = relationship('Aluno', back_populates='fada_avaliacoes')
    avaliador: Mapped['User'] = relationship('User')

    # 18 Atributos (conforme PDF)
    attr_1_expressao: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)
    attr_2_planejamento: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)
    attr_3_perseveranca: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)
    attr_4_apresentacao: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)
    attr_5_lealdade: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)
    attr_6_tato: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)
    attr_7_equilibrio: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)
    attr_8_disciplina: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)
    attr_9_responsabilidade: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)
    attr_10_maturidade: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)
    attr_11_assiduidade: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)
    attr_12_pontualidade: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)
    attr_13_diccao: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)
    attr_14_lideranca: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)
    attr_15_relacionamento: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)
    attr_16_etica: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)
    attr_17_produtividade: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)
    attr_18_eficiencia: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)

    # Campos de texto
    justificativa_notas: Mapped[t.Optional[str]] = mapped_column(Text)
    observacoes: Mapped[t.Optional[str]] = mapped_column(Text)
    
    adaptacao_carreira: Mapped[str] = mapped_column(String(50), nullable=False, default='Em adaptação à carreira militar')

    # Relação de volta no Aluno
    # Adicionar em 'aluno.py':
    # fada_avaliacoes: Mapped[list['FadaAvaliacao']] = relationship('FadaAvaliacao', back_populates='aluno', lazy='dynamic')
    
    # Relação de volta no User (para o avaliador)
    # Não precisa de back_populates se for só para ler

    def __repr__(self):
        return f"<FadaAvaliacao id={self.id} aluno_id={self.aluno_id}>"