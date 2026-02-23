# backend/models/processo_disciplina.py
from __future__ import annotations
import typing as t
import enum
from datetime import datetime, timedelta

from sqlalchemy import ForeignKey, String, Float, Text, Boolean, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .database import db

if t.TYPE_CHECKING:
    from .aluno import Aluno
    from .user import User
    from .discipline_rule import DisciplineRule

class StatusProcesso(str, enum.Enum):
    AGUARDANDO_CIENCIA = "AGUARDANDO_CIENCIA"
    ALUNO_NOTIFICADO = "ALUNO_NOTIFICADO"
    DEFESA_ENVIADA = "DEFESA_ENVIADA"
    EM_ANALISE = "EM_ANALISE"         # Analise do Chefe CAL
    DECISAO_EMITIDA = "DECISAO_EMITIDA" # Chefe decidiu, aguardando ciencia do aluno
    EM_RECURSO = "EM_RECURSO"         # Aluno recorreu ao Comandante
    FINALIZADO = "FINALIZADO"         # Encerrado
    ARQUIVADO = "ARQUIVADO"

class ProcessoDisciplina(db.Model):
    __tablename__ = 'processos_disciplina'

    id: Mapped[int] = mapped_column(primary_key=True)

    aluno_id: Mapped[int] = mapped_column(ForeignKey('alunos.id'), nullable=False)
    relator_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    regra_id: Mapped[t.Optional[int]] = mapped_column(ForeignKey('discipline_rules.id'), nullable=True)

    codigo_infracao: Mapped[t.Optional[str]] = mapped_column(String(50), nullable=True)
    fato_constatado: Mapped[str] = mapped_column(Text, nullable=False)
    observacao: Mapped[t.Optional[str]] = mapped_column(Text, nullable=True)
    pontos: Mapped[float] = mapped_column(Float, default=0.0)

    # Status definido como String no banco para evitar travamento de ENUM
    status: Mapped[str] = mapped_column(
        String(50),
        default=StatusProcesso.AGUARDANDO_CIENCIA.value,
        server_default=StatusProcesso.AGUARDANDO_CIENCIA.value,
        nullable=False
    )

    # DATAS FLUXO
    data_ocorrencia: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    data_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    data_ciente: Mapped[t.Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Propriedade auxiliar para compatibilidade
    @property
    def data_ciencia(self):
        return self.data_ciente
    
    @data_ciencia.setter
    def data_ciencia(self, value):
        self.data_ciente = value

    data_defesa: Mapped[t.Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    data_decisao: Mapped[t.Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # FLUXO RECURSAL
    data_notificacao_decisao: Mapped[t.Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    data_recurso: Mapped[t.Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    data_julgamento_recurso: Mapped[t.Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # TEXTOS
    defesa: Mapped[t.Optional[str]] = mapped_column(Text, nullable=True)
    decisao_final: Mapped[t.Optional[str]] = mapped_column(String(50), nullable=True)
    fundamentacao: Mapped[t.Optional[str]] = mapped_column(Text, nullable=True)
    observacao_decisao: Mapped[t.Optional[str]] = mapped_column(Text, nullable=True)
    detalhes_sancao: Mapped[t.Optional[str]] = mapped_column(Text, nullable=True)

    # RECURSO
    texto_recurso: Mapped[t.Optional[str]] = mapped_column(Text, nullable=True)
    decisao_recurso: Mapped[t.Optional[str]] = mapped_column(String(50), nullable=True)
    fundamentacao_recurso: Mapped[t.Optional[str]] = mapped_column(Text, nullable=True)
    autoridade_recurso_id: Mapped[t.Optional[int]] = mapped_column(ForeignKey('users.id'), nullable=True)

    # OUTROS
    is_crime: Mapped[bool] = mapped_column(Boolean, default=False)
    tipo_sancao: Mapped[t.Optional[str]] = mapped_column(String(50), nullable=True)
    dias_sancao: Mapped[int] = mapped_column(Integer, default=0)
    origem_punicao: Mapped[str] = mapped_column(String(20), default='NPCCAL')
    ciente_aluno: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # NOVO: Controle de Revelia
    is_revelia: Mapped[bool] = mapped_column(Boolean, default=False)

    # RELACIONAMENTOS
    aluno = relationship("Aluno", backref=db.backref("processos_novos", overlaps="processos_disciplinares"))
    relator: Mapped["User"] = relationship(foreign_keys=[relator_id])
    autoridade_recurso: Mapped[t.Optional["User"]] = relationship(foreign_keys=[autoridade_recurso_id])
    regra: Mapped[t.Optional["DisciplineRule"]] = relationship()

    # --- PROPRIEDADES DE CÁLCULO DE PRAZO (USADAS NO FRONTEND) ---
    @property
    def prazo_ciencia(self):
        if self.data_registro:
            return self.data_registro + timedelta(hours=24)
        return None

    @property
    def prazo_defesa(self):
        if self.data_ciente:
            return self.data_ciente + timedelta(hours=24)
        return None

    @property
    def prazo_recurso(self):
        if self.data_notificacao_decisao:
            return self.data_notificacao_decisao + timedelta(hours=48)
        return None

    def __repr__(self):
        return f"<Processo {self.id} - Aluno {self.aluno_id} - {self.status}>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'aluno_nome': self.aluno.user.nome_completo if self.aluno and self.aluno.user else "Desconhecido",
            'turma': self.aluno.turma.nome if self.aluno and self.aluno.turma else "N/A",
            'data_ocorrencia': self.data_ocorrencia.strftime('%d/%m/%Y'),
            'fato': self.fato_constatado,
            'status': self.status,
            'pontos': self.pontos,
            'decisao': self.decisao_final,
            'fundamentacao': self.fundamentacao or self.observacao_decisao,
            'is_revelia': self.is_revelia
        }