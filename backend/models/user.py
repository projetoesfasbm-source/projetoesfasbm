# backend/models/user.py

from __future__ import annotations
import typing as t
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship, Mapped, mapped_column
from .database import db

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
    ROLE_ADMIN_CAL = 'admin_cal'   # Novo: Chefe CAL (Justiça)
    ROLE_ADMIN_SENS = 'admin_sens' # Novo: Chefe SENS (Ensino)
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

    # --- RELACIONAMENTOS ORIGINAIS (INTOCADOS) ---
    aluno_profile: Mapped['Aluno'] = relationship('Aluno', back_populates='user', uselist=False, cascade="all, delete-orphan")
    instrutor_profile: Mapped['Instrutor'] = relationship('Instrutor', back_populates='user', uselist=False, cascade="all, delete-orphan")
    user_schools: Mapped[list['UserSchool']] = relationship('UserSchool', back_populates='user', cascade="all, delete-orphan")

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

    # --- PROPRIEDADES DE PODER (QUEM É O CHEFE DE QUÊ) ---
    # Isso define quem pode EDITAR/GERENCIAR. 
    # A visualização no menu será controlada separadamente no HTML.

    @property
    def is_programador(self):
        return self.role == self.ROLE_PROGRAMADOR

    @property
    def is_admin_escola(self):
        # Comandante / Acesso Total
        return self.role == self.ROLE_ADMIN_ESCOLA

    @property
    def is_cal(self):
        # É o ADMINISTRADOR da Justiça? (Chefe CAL, Comandante ou Programador)
        return self.role in [self.ROLE_ADMIN_CAL, self.ROLE_ADMIN_ESCOLA, self.ROLE_PROGRAMADOR]

    @property
    def is_sens(self):
        # É o ADMINISTRADOR do Ensino? (Chefe SENS, Comandante ou Programador)
        return self.role in [self.ROLE_ADMIN_SENS, self.ROLE_ADMIN_ESCOLA, self.ROLE_PROGRAMADOR]

    @property
    def is_staff(self):
        # Faz parte da equipe administrativa (SENS, CAL, Comandante)
        return self.role in [self.ROLE_ADMIN_SENS, self.ROLE_ADMIN_CAL, self.ROLE_ADMIN_ESCOLA, self.ROLE_PROGRAMADOR]