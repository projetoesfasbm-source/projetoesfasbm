# backend/models/user.py
from .database import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    # Constantes de Permissão
    ROLE_PROGRAMADOR = 'programador'
    ROLE_ADMIN_ESCOLA = 'admin_escola'
    ROLE_ADMIN_CAL = 'admin_cal'   # Novo: Corpo de Alunos
    ROLE_ADMIN_SENS = 'admin_sens' # Novo: Seção de Ensino
    ROLE_INSTRUTOR = 'instrutor'
    ROLE_ALUNO = 'aluno'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    nome_completo = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=True)
    
    # Campo de Função/Cargo (Ex: 'admin_escola', 'admin_cal', 'admin_sens', 'aluno')
    role = db.Column(db.String(50), nullable=False, default=ROLE_ALUNO)
    
    posto_graduacao = db.Column(db.String(50), nullable=True)
    matricula = db.Column(db.String(50), unique=True, nullable=True)

    # Relacionamentos
    instrutor_profile = db.relationship('Instrutor', backref='user', uselist=False, cascade="all, delete-orphan")
    aluno_profile = db.relationship('Aluno', backref='user', uselist=False, cascade="all, delete-orphan")
    
    # Escolas vinculadas
    schools = db.relationship('UserSchool', back_populates='user', cascade="all, delete-orphan")
    
    # Notificações e Push
    push_subscriptions = db.relationship('PushSubscription', backref='user', lazy=True, cascade="all, delete-orphan")
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # --- Propriedades de Verificação de Permissão Auxiliares ---

    @property
    def is_programador(self):
        return self.role == self.ROLE_PROGRAMADOR

    @property
    def is_admin_escola(self):
        return self.role == self.ROLE_ADMIN_ESCOLA

    @property
    def is_cal(self):
        # CAL ou Superior (Admin Escola/Programador)
        return self.role in [self.ROLE_ADMIN_CAL, self.ROLE_ADMIN_ESCOLA, self.ROLE_PROGRAMADOR]

    @property
    def is_sens(self):
        # SENS ou Superior (Admin Escola/Programador)
        return self.role in [self.ROLE_ADMIN_SENS, self.ROLE_ADMIN_ESCOLA, self.ROLE_PROGRAMADOR]