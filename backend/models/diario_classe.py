# backend/models/diario_classe.py
from __future__ import annotations
import typing as t
from datetime import date, datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Integer, String, Text, DateTime
from .database import db

if t.TYPE_CHECKING:
    from .turma import Turma
    from .disciplina import Disciplina
    from .user import User
    from .frequencia import FrequenciaAluno

class DiarioClasse(db.Model):
    __tablename__ = 'diarios_classe'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data_aula: Mapped[date] = mapped_column(db.Date, nullable=False)
    
    # Campo original mantido
    periodo: Mapped[t.Optional[int]] = mapped_column(Integer, nullable=True)

    # Vínculos Originais
    turma_id: Mapped[int] = mapped_column(ForeignKey('turmas.id'), nullable=False)
    disciplina_id: Mapped[int] = mapped_column(ForeignKey('disciplinas.id'), nullable=False)
    responsavel_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    
    # Conteúdo
    conteudo_ministrado: Mapped[t.Optional[str]] = mapped_column(Text)
    observacoes: Mapped[t.Optional[str]] = mapped_column(Text)
    
    # --- NOVOS CAMPOS PARA ASSINATURA E VALIDAÇÃO ---
    status: Mapped[str] = mapped_column(String(20), default='pendente', nullable=False)
    assinatura_path: Mapped[t.Optional[str]] = mapped_column(String(255), nullable=True)
    data_assinatura: Mapped[t.Optional[datetime]] = mapped_column(DateTime, nullable=True)
    instrutor_assinante_id: Mapped[t.Optional[int]] = mapped_column(ForeignKey('users.id'), nullable=True)

    # Metadados
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relacionamentos
    turma: Mapped["Turma"] = relationship()
    
    # Atualizado para linkar com o cascade da Disciplina
    disciplina: Mapped["Disciplina"] = relationship(back_populates="diarios")
    
    # Relacionamento com quem preencheu (Chefe)
    responsavel: Mapped["User"] = relationship(foreign_keys=[responsavel_id])
    
    # Relacionamento CRÍTICO para FrequenciaAluno (Restaurado)
    frequencias: Mapped[list["FrequenciaAluno"]] = relationship(back_populates="diario", cascade="all, delete-orphan")
    
    # Novo relacionamento para o Instrutor que assinou
    instrutor_assinante: Mapped["User"] = relationship(foreign_keys=[instrutor_assinante_id])

    def __repr__(self):
        return f"<DiarioClasse id={self.id} data={self.data_aula} status={self.status}>"