# backend/models/user.py

from __future__ import annotations
import typing as t
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship, Mapped, mapped_column
from .database import db
from flask import session # Mantemos como fallback

if t.TYPE_CHECKING:
    from .site_config import SiteConfig
    from .school import School
    from .user_school import UserSchool
    from .aluno import Aluno
    from .instrutor import Instrutor
    from .notification import Notification
    from .push_subscription import PushSubscription

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    # --- CONSTANTES DE PERMISSÃO ---
    ROLE_PROGRAMADOR = 'programador'
    ROLE_ADMIN_ESCOLA = 'admin_escola' # Comandante
    ROLE_ADMIN_CAL = 'admin_cal'       # Chefe CAL
    ROLE_ADMIN_SENS = 'admin_sens'     # Chefe SENS
    ROLE_INSTRUTOR = 'instrutor'
    ROLE_ALUNO = 'aluno'

    id: Mapped[int] = mapped_column(primary_key=True)
    matricula: Mapped[str] = mapped_column(db.String(20), unique=True, nullable=False)
    username: Mapped[t.Optional[str]] = mapped_column(db.String(80), unique=True, nullable=True)
    email: Mapped[t.Optional[str]] = mapped_column(db.String(120), unique=True, nullable=True)
    password_hash: Mapped[t.Optional[str]] = mapped_column(db.String(256), nullable=True)
    nome_completo: Mapped[t.Optional[str]] = mapped_column(db.String(120), nullable=True)
    nome_de_guerra: Mapped[t.Optional[str]] = mapped_column(db.String(50), nullable=True)
    posto_graduacao: Mapped[t.Optional[str]] = mapped_column(db.String(50), nullable=True)
    
    role: Mapped[str] = mapped_column(db.String(20), nullable=False, default='aluno')
    
    is_active: Mapped[bool] = mapped_column(default=False, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(default=False, nullable=False)

    # --- RELACIONAMENTOS ---
    aluno_profile: Mapped['Aluno'] = relationship('Aluno', back_populates='user', uselist=False, cascade="all, delete-orphan")
    instrutor_profile: Mapped['Instrutor'] = relationship('Instrutor', back_populates='user', uselist=False, cascade="all, delete-orphan")
    # Carregamento eager para garantir que as permissões estejam disponíveis
    user_schools: Mapped[list['UserSchool']] = relationship('UserSchool', back_populates='user', cascade="all, delete-orphan", lazy='selectin')

    notifications: Mapped[list['Notification']] = relationship('Notification', back_populates='user', cascade="all, delete-orphan")
    push_subscriptions: Mapped[list['PushSubscription']] = relationship('PushSubscription', back_populates='user', cascade="all, delete-orphan")

    @property
    def schools(self) -> list['School']:
        return [us.school for us in self.user_schools]

    site_configs_updated: Mapped[list['SiteConfig']] = relationship('SiteConfig', back_populates='updated_by_user')

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username or self.matricula}>'

    # =================================================================
    # LÓGICA DE PERMISSÕES (CORRIGIDA)
    # =================================================================

    def _get_active_school_id(self):
        """Tenta recuperar o ID da escola ativa do contexto ou sessão."""
        # 1. Verifica se foi injetado pelo before_request (mais seguro)
        if hasattr(self, 'temp_active_school_id'):
            return self.temp_active_school_id
        # 2. Fallback para sessão direta
        try:
            sid = session.get('active_school_id')
            return int(sid) if sid else None
        except:
            return None

    def get_role_in_school(self, school_id: int | None) -> str:
        """Retorna o cargo do usuário na escola específica."""
        # Super usuários globais
        if self.role == self.ROLE_PROGRAMADOR: return self.ROLE_PROGRAMADOR
        if self.role == 'super_admin': return 'super_admin'
            
        if not school_id:
            return self.role 
            
        # Busca na lista (agora carregada com lazy='selectin' para garantir)
        for us in self.user_schools:
            if us.school_id == int(school_id):
                return us.role
        
        return self.ROLE_ALUNO

    # --- Verificadores Contextuais (passando ID explícito) ---

    def is_programador_check(self) -> bool:
        return self.role == self.ROLE_PROGRAMADOR

    def is_admin_escola_in_school(self, school_id: int | None) -> bool:
        if self.is_programador_check(): return True
        return self.get_role_in_school(school_id) == self.ROLE_ADMIN_ESCOLA

    def is_cal_in_school(self, school_id: int | None) -> bool:
        if self.is_programador_check(): return True
        role = self.get_role_in_school(school_id)
        # CAL é Admin ou CAL
        return role in [self.ROLE_ADMIN_CAL, self.ROLE_ADMIN_ESCOLA]

    def is_sens_in_school(self, school_id: int | None) -> bool:
        if self.is_programador_check(): return True
        role = self.get_role_in_school(school_id)
        # SENS é Admin ou SENS
        return role in [self.ROLE_ADMIN_SENS, self.ROLE_ADMIN_ESCOLA]
        
    def is_instrutor_in_school(self, school_id: int | None) -> bool:
        if self.is_programador_check(): return True
        role = self.get_role_in_school(school_id)
        return role == self.ROLE_INSTRUTOR

    def is_staff_in_school(self, school_id: int | None) -> bool:
        if self.is_programador_check(): return True
        role = self.get_role_in_school(school_id)
        return role in [self.ROLE_ADMIN_SENS, self.ROLE_ADMIN_CAL, self.ROLE_ADMIN_ESCOLA]

    # --- PROPRIEDADES LEGADAS INTELIGENTES (RESOLUÇÃO DO PROBLEMA) ---
    # Estas propriedades agora buscam automaticamente a escola ativa.
    
    @property
    def is_programador(self):
        return self.role == self.ROLE_PROGRAMADOR

    @property
    def is_admin_escola(self):
        # Admin Geral: Tem acesso a tudo que SENS e CAL têm
        if self.is_programador: return True
        sid = self._get_active_school_id()
        return self.is_admin_escola_in_school(sid)

    @property
    def is_cal(self):
        # Quem é Admin Escola TAMBÉM é CAL (tem permissão de justiça)
        sid = self._get_active_school_id()
        return self.is_cal_in_school(sid)

    @property
    def is_sens(self):
        # Quem é Admin Escola TAMBÉM é SENS (tem permissão de ensino)
        sid = self._get_active_school_id()
        return self.is_sens_in_school(sid)

    @property
    def is_staff(self):
        sid = self._get_active_school_id()
        return self.is_staff_in_school(sid)