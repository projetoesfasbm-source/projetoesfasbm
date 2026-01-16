from datetime import datetime
from typing import Optional
from sqlalchemy import ForeignKey, String, Float, Text, Boolean, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import db

# --- CONSTANTES DE STATUS ---
# Ajustado para corresponder exatamente ao que deve estar no banco ou ser flexível
class StatusProcesso:
    AGUARDANDO_CIENCIA = "Aguardando Ciência"
    ALUNO_NOTIFICADO = "Aluno Notificado"
    DEFESA_ENVIADA = "Defesa Enviada"
    EM_ANALISE = "Em Análise"
    FINALIZADO = "Finalizado" # Padronizado para Title Case

class ProcessoDisciplina(db.Model):
    __tablename__ = 'processos_disciplina'

    id: Mapped[int] = mapped_column(primary_key=True)
    
    aluno_id: Mapped[int] = mapped_column(ForeignKey('alunos.id'), nullable=False)
    relator_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    regra_id: Mapped[Optional[int]] = mapped_column(ForeignKey('discipline_rules.id'), nullable=True)

    codigo_infracao: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    fato_constatado: Mapped[str] = mapped_column(Text, nullable=False)
    observacao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pontos: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Status como String
    status: Mapped[str] = mapped_column(String(50), default=StatusProcesso.AGUARDANDO_CIENCIA)
    
    data_ocorrencia: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    data_ciente: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    data_defesa: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    data_decisao: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    defesa: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decisao_final: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    fundamentacao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    detalhes_sancao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Campos de Punição
    is_crime: Mapped[bool] = mapped_column(Boolean, default=False)
    tipo_sancao: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    dias_sancao: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    origem_punicao: Mapped[str] = mapped_column(String(20), default='NPCCAL')

    ciente_aluno: Mapped[bool] = mapped_column(Boolean, default=False)

    aluno = relationship("Aluno", backref="processos_disciplina")
    relator = relationship("User", foreign_keys=[relator_id])
    regra = relationship("DisciplineRule")