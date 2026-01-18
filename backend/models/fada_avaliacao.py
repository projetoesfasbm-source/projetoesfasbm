# backend/models/fada_avaliacao.py
from datetime import datetime
from typing import Optional
from sqlalchemy import ForeignKey, Float, Text, DateTime, String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import db

class FadaAvaliacao(db.Model):
    __tablename__ = 'fada_avaliacoes'

    id: Mapped[int] = mapped_column(primary_key=True)
    aluno_id: Mapped[int] = mapped_column(ForeignKey('alunos.id'), nullable=False)
    
    # Responsável pelo lançamento (Chefe CAL/SENS)
    lancador_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    
    # --- COMISSÃO DE AVALIAÇÃO (IDs dos Usuários) ---
    presidente_id: Mapped[Optional[int]] = mapped_column(ForeignKey('users.id'), nullable=True)
    membro1_id: Mapped[Optional[int]] = mapped_column(ForeignKey('users.id'), nullable=True)
    membro2_id: Mapped[Optional[int]] = mapped_column(ForeignKey('users.id'), nullable=True)

    data_avaliacao: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    observacao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- NOTAS DOS 18 ATRIBUTOS ---
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

    # --- FLUXO E AUDITORIA ---
    status: Mapped[str] = mapped_column(String(20), default='RASCUNHO') 
    # Etapas: RASCUNHO -> COMISSAO -> ALUNO -> FINALIZADO
    etapa_atual: Mapped[str] = mapped_column(String(50), default='RASCUNHO')
    
    # Snapshots para Integridade Jurídica (Congela nota no envio)
    ndisc_snapshot: Mapped[float] = mapped_column(Float, default=0.0)
    aat_snapshot: Mapped[float] = mapped_column(Float, default=0.0)
    data_envio: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # --- ASSINATURAS DIGITAIS DA COMISSÃO ---
    # Presidente
    data_ass_pres: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    hash_pres: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ip_pres: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    # Membro 1
    data_ass_m1: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    hash_m1: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ip_m1: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    # Membro 2
    data_ass_m2: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    hash_m2: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ip_m2: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    # --- ASSINATURA DO ALUNO ---
    data_assinatura: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    hash_integridade: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ip_assinatura: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent_aluno: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    texto_recurso: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relacionamentos
    aluno = relationship("Aluno")
    lancador = relationship("User", foreign_keys=[lancador_id])
    
    presidente = relationship("User", foreign_keys=[presidente_id])
    membro1 = relationship("User", foreign_keys=[membro1_id])
    membro2 = relationship("User", foreign_keys=[membro2_id])

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