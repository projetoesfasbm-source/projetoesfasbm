# backend/models/discipline_rule.py
from typing import Optional
from .database import db
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Float, Text

class DisciplineRule(db.Model):
    """
    Armazena as regras de disciplina (infrações) de um NPCCAL específico.
    """
    __tablename__ = 'discipline_rules'

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # 'ctsp' (Sargentos), 'cbfpm' (Soldados), 'cspm' (Oficiais)
    npccal_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    
    # Código da infração (ex: "1", "2", "R-1")
    codigo: Mapped[str] = mapped_column(String(10), nullable=False)
    
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    
    # --- MUDANÇA AQUI: Gravidade agora é OPCIONAL (nullable=True) ---
    # CSPM não usa gravidade, apenas pontos.
    gravidade: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # ----------------------------------------------------------------
    
    pontos: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    def __repr__(self):
        return f"<DisciplineRule {self.npccal_type} - {self.codigo}>"