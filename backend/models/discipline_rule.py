from typing import Optional
from .database import db
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Float, Text, Integer

class DisciplineRule(db.Model):
    """
    Armazena as regras de disciplina (infrações) de um NPCCAL específico.
    """
    __tablename__ = 'discipline_rules'

    id: Mapped[int] = mapped_column(primary_key=True)
    # 'ctsp', 'cbfpm', 'cspm'
    npccal_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    
    codigo: Mapped[str] = mapped_column(String(10), nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    gravidade: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    pontos: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # NOVO: Qual atributo da FADA (1-18) esta infração afeta?
    atributo_fada_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    def __repr__(self):
        return f"<DisciplineRule {self.npccal_type} - {self.codigo}>"