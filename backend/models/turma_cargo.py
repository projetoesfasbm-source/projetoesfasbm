# backend/models/turma_cargo.py
from __future__ import annotations
import typing as t
from .database import db
from sqlalchemy.orm import Mapped, mapped_column, relationship

if t.TYPE_CHECKING:
    from .turma import Turma
    from .aluno import Aluno

class TurmaCargo(db.Model):
    __tablename__ = 'turma_cargos'

    # --- DEFINIÇÃO DE CARGOS PADRÃO (CONSTANTES) ---
    # Use estas constantes em todo o sistema em vez de strings soltas
    ROLE_CHEFE = "Chefe de Turma"
    ROLE_SUBCHEFE = "Sub-Chefe"
    ROLE_AUXILIAR = "Auxiliar do Pelotão"
    ROLE_C1 = "C1"
    ROLE_C2 = "C2"
    ROLE_C3 = "C3"
    ROLE_C4 = "C4"
    ROLE_C5 = "C5"

    @classmethod
    def get_all_roles(cls):
        """Retorna a lista oficial de cargos permitidos."""
        return [
            cls.ROLE_AUXILIAR, 
            cls.ROLE_CHEFE, 
            cls.ROLE_SUBCHEFE,
            cls.ROLE_C1, cls.ROLE_C2, cls.ROLE_C3, cls.ROLE_C4, cls.ROLE_C5
        ]
    # -----------------------------------------------

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Nome do cargo (agora padronizado pelas constantes acima)
    cargo_nome: Mapped[str] = mapped_column(db.String(100), nullable=False)
    
    turma_id: Mapped[int] = mapped_column(db.ForeignKey('turmas.id'), nullable=False)
    aluno_id: Mapped[t.Optional[int]] = mapped_column(db.ForeignKey('alunos.id'), nullable=True)

    turma: Mapped["Turma"] = relationship()
    aluno: Mapped[t.Optional["Aluno"]] = relationship()

    def __init__(self, turma_id: int, cargo_nome: str, aluno_id: t.Optional[int] = None, **kw: t.Any) -> None:
        super().__init__(turma_id=turma_id, cargo_nome=cargo_nome, aluno_id=aluno_id, **kw)

    def __repr__(self):
        return f"<TurmaCargo id={self.id} turma_id={self.turma_id} cargo='{self.cargo_nome}' aluno_id={self.aluno_id}>"