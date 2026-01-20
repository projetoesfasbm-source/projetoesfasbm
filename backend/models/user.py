from __future__ import annotations
import typing as t
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship, Mapped, mapped_column
from .database import db
from flask import session

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
    ROLE_ADMIN_ESCOLA = 'admin_escola'
    ROLE_ADMIN_CAL = 'admin_cal'
    ROLE_ADMIN_SENS = 'admin_sens'
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
    # useList=False garante que seja tratado como objeto único (1-to-1)
    aluno_profile: Mapped['Aluno'] = relationship('Aluno', back_populates='user', uselist=False, cascade="all, delete-orphan")
    instrutor_profile: Mapped['Instrutor'] = relationship('Instrutor', back_populates='user', uselist=False, cascade="all, delete-orphan")
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
    # LÓGICA DE PERMISSÕES
    # =================================================================

    def _get_active_school_id(self):
        if hasattr(self, 'temp_active_school_id'):
            return self.temp_active_school_id
        try:
            sid = session.get('active_school_id')
            return int(sid) if sid else None
        except:
            return None

    def get_role_in_school(self, school_id: int | str | None) -> str:
        current_global_role = str(self.role).lower().strip()
        if current_global_role == self.ROLE_PROGRAMADOR: return self.ROLE_PROGRAMADOR
        if current_global_role == 'super_admin': return 'super_admin'
            
        if not school_id:
            return current_global_role
            
        for us in self.user_schools:
            # COMPARAÇÃO ROBUSTA (STR vs STR)
            if str(us.school_id) == str(school_id):
                return str(us.role).lower().strip()
        
        return self.ROLE_ALUNO

    # --- Verificadores Contextuais ---

    def is_programador_check(self) -> bool:
        return str(self.role).lower().strip() == self.ROLE_PROGRAMADOR

    def is_admin_escola_in_school(self, school_id: int | None) -> bool:
        if self.is_programador_check(): return True
        return self.get_role_in_school(school_id) == self.ROLE_ADMIN_ESCOLA

    def is_cal_in_school(self, school_id: int | None) -> bool:
        if self.is_programador_check(): return True
        role = self.get_role_in_school(school_id)
        return role in [self.ROLE_ADMIN_CAL, self.ROLE_ADMIN_ESCOLA]

    def is_sens_in_school(self, school_id: int | None) -> bool:
        """SENS inclui ADMIN_SENS e ADMIN_ESCOLA (Comandante tem acesso total)"""
        if self.is_programador_check(): return True
        role = self.get_role_in_school(school_id)
        return role in [self.ROLE_ADMIN_SENS, self.ROLE_ADMIN_ESCOLA]
        
    def is_instrutor_in_school(self, school_id: int | None) -> bool:
        if self.is_programador_check(): return True
        role = self.get_role_in_school(school_id)
        return role == self.ROLE_INSTRUTOR

    def is_staff_in_school(self, school_id: int | None) -> bool:
        """Staff inclui SENS, CAL e Comandante"""
        if self.is_programador_check(): return True
        role = self.get_role_in_school(school_id)
        return role in [self.ROLE_ADMIN_SENS, self.ROLE_ADMIN_CAL, self.ROLE_ADMIN_ESCOLA]

    # --- PROPRIEDADES INTELIGENTES ---
    
    @property
    def is_programador(self):
        return self.is_programador_check()

    @property
    def is_admin_escola(self):
        sid = self._get_active_school_id()
        return self.is_admin_escola_in_school(sid)

    @property
    def is_cal(self):
        sid = self._get_active_school_id()
        return self.is_cal_in_school(sid)

    @property
    def is_sens(self):
        sid = self._get_active_school_id()
        return self.is_sens_in_school(sid)

    @property
    def is_staff(self):
        sid = self._get_active_school_id()
        return self.is_staff_in_school(sid)