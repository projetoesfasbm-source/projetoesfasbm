# backend/models/diario_classe.py
from __future__ import annotations
import typing as t
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Integer, String, Text, DateTime
from .database import db

if t.TYPE_CHECKING:
    from .horario import Horario
    from .user import User

class DiarioClasse(db.Model):
    __tablename__ = 'diarios_classe'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Vinculo com o Horário (Aula específica)
    horario_id: Mapped[int] = mapped_column(ForeignKey('horarios.id'), nullable=False)
    horario: Mapped["Horario"] = relationship("Horario", backref="diarios")

    # Data da aula (pois o horario é semanal, mas o diario é diario)
    data_aula: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Conteúdo (preenchido pelo aluno/chefe)
    conteudo_ministrado: Mapped[str] = mapped_column(Text, nullable=True)
    observacoes: Mapped[str] = mapped_column(Text, nullable=True)
    
    # --- NOVOS CAMPOS PARA ASSINATURA E VALIDAÇÃO ---
    # Status: 'pendente' (padrão) ou 'assinado'
    status: Mapped[str] = mapped_column(String(20), default='pendente', nullable=False)
    
    # Caminho para a imagem da assinatura no disco (static/uploads/signatures/...)
    assinatura_path: Mapped[str] = mapped_column(String(255), nullable=True)
    
    # Data e Hora exata da assinatura
    data_assinatura: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # ID do usuário (Instrutor) que assinou
    instrutor_assinante_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=True)
    instrutor_assinante: Mapped["User"] = relationship("User", foreign_keys=[instrutor_assinante_id])

    # Metadados de criação (Aluno que lançou)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<DiarioClasse id={self.id} data={self.data_aula} status={self.status}>"