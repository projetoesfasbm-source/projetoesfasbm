from datetime import datetime
from typing import Optional
from sqlalchemy import ForeignKey, Float, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import db

class FadaAvaliacao(db.Model):
    __tablename__ = 'fada_avaliacoes'

    id: Mapped[int] = mapped_column(primary_key=True)
    aluno_id: Mapped[int] = mapped_column(ForeignKey('alunos.id'), nullable=False)
    avaliador_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    
    data_avaliacao: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    observacao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Notas
    expressao: Mapped[float] = mapped_column(Float, default=0.0)
    planejamento: Mapped[float] = mapped_column(Float, default=0.0)
    perseveranca: Mapped[float] = mapped_column(Float, default=0.0)
    apresentacao: Mapped[float] = mapped_column(Float, default=0.0)
    lealdade: Mapped[float] = mapped_column(Float, default=0.0)
    tato: Mapped[float] = mapped_column(Float, default=0.0)
    equilibrio: Mapped[float] = mapped_column(Float, default=0.0)
    disciplina: Mapped[float] = mapped_column(Float, default=0.0)
    responsabilidade: Mapped[float] = mapped_column(Float, default=0.0)
    maturidade: Mapped[float] = mapped_column(Float, default=0.0)
    assiduidade: Mapped[float] = mapped_column(Float, default=0.0)
    pontualidade: Mapped[float] = mapped_column(Float, default=0.0)
    diccao: Mapped[float] = mapped_column(Float, default=0.0)
    lideranca: Mapped[float] = mapped_column(Float, default=0.0)
    relacionamento: Mapped[float] = mapped_column(Float, default=0.0)
    etica: Mapped[float] = mapped_column(Float, default=0.0)
    produtividade: Mapped[float] = mapped_column(Float, default=0.0)
    eficiencia: Mapped[float] = mapped_column(Float, default=0.0)

    media_final: Mapped[float] = mapped_column(Float, default=0.0)

    # CORREÇÃO CIRÚRGICA: Backref removido para evitar conflito com 'Aluno'
    aluno = relationship("Aluno")
    avaliador = relationship("User")

    def calcular_media(self):
        atributos = [
            self.expressao, self.planejamento, self.perseveranca, self.apresentacao,
            self.lealdade, self.tato, self.equilibrio, self.disciplina,
            self.responsabilidade, self.maturidade, self.assiduidade, self.pontualidade,
            self.diccao, self.lideranca, self.relacionamento, self.etica,
            self.produtividade, self.eficiencia
        ]
        validos = [a for a in atributos if a is not None]
        if validos:
            self.media_final = sum(validos) / len(validos)
        else:
            self.media_final = 0.0