# tests/conftest.py

import pytest
from backend.app import create_app
from backend.models.database import db as _db
from backend.models.user import User
from backend.models.school import School
from backend.models.user_school import UserSchool
from backend.models.aluno import Aluno
from backend.models.turma import Turma
from backend.config import Config
from flask_login import login_user, logout_user

class TestingConfig(Config):
    """Configuração dedicada para o ambiente de testes."""
    TESTING = True
    SECRET_KEY = "uma-chave-secreta-para-testes"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False

    @staticmethod
    def init_app(app):
        pass

@pytest.fixture(scope='function')
def test_app():
    """Cria e configura uma instância da aplicação para cada teste."""
    app = create_app(config_class=TestingConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()

@pytest.fixture(scope='function')
def db_session(test_app):
    """Fornece a sessão do banco de dados da aplicação."""
    with test_app.app_context():
        yield _db.session

@pytest.fixture(scope='function')
def test_client(test_app):
    """Cria um cliente de teste para simular requisições HTTP."""
    return test_app.test_client()

@pytest.fixture(scope='function')
def new_user(db_session):
    """Fixture para criar um novo usuário padrão."""
    user = User(username='testuser', id_func='12345', email='test@example.com', role='aluno', is_active=True)
    user.set_password('password123')
    db_session.add(user)
    db_session.commit()
    return user

@pytest.fixture(scope='function')
def logged_in_user(test_app, new_user):
    """Fixture para simular um usuário logado."""
    with test_app.test_request_context():
        login_user(new_user)
        yield new_user
        logout_user()

@pytest.fixture(scope='function')
def new_super_admin(db_session):
    """Fixture para criar um novo usuário super_admin."""
    admin = User(username='superadmin', id_func='54321', email='admin@example.com', role='super_admin', is_active=True)
    admin.set_password('adminpass')
    db_session.add(admin)
    db_session.commit()
    return admin

@pytest.fixture(scope='function')
def logged_in_super_admin(test_app, new_super_admin):
    """Fixture para simular um super_admin logado."""
    with test_app.test_request_context():
        login_user(new_super_admin)
        yield new_super_admin
        logout_user()

@pytest.fixture(scope='function')
def setup_school_with_users(db_session):
    """
    Cria uma escola, um admin para a escola e dois alunos em uma turma
    para usar como base em outros testes de serviço.
    """
    # 1. Cria a Escola
    school = School(nome="Escola de Testes Base")
    db_session.add(school)
    db_session.commit()

    # 2. Cria a Turma
    turma = Turma(nome="1º Pelotão Base", ano=2025, school_id=school.id)
    db_session.add(turma)
    db_session.commit()

    # 3. Cria o Admin
    admin_user = User(id_func='admin_base', nome_completo='Admin Base', role='admin_escola', is_active=True)
    db_session.add(admin_user)
    db_session.commit()
    db_session.add(UserSchool(user_id=admin_user.id, school_id=school.id, role='admin_escola'))

    # 4. Cria os Alunos
    user_aluno1 = User(id_func='aluno_base1', nome_completo='Aluno Base Um', role='aluno', is_active=True)
    user_aluno2 = User(id_func='aluno_base2', nome_completo='Aluno Base Dois', role='aluno', is_active=True)
    db_session.add_all([user_aluno1, user_aluno2])
    db_session.commit()

    aluno1 = Aluno(user_id=user_aluno1.id, matricula='m_base1', opm="OPM Base", turma_id=turma.id)
    aluno2 = Aluno(user_id=user_aluno2.id, matricula='m_base2', opm="OPM Base", turma_id=turma.id)
    db_session.add_all([aluno1, aluno2])
    db_session.commit()

    db_session.add_all([
        UserSchool(user_id=user_aluno1.id, school_id=school.id, role='aluno'),
        UserSchool(user_id=user_aluno2.id, school_id=school.id, role='aluno')
    ])
    db_session.commit()
    
    return school, admin_user, [aluno1, aluno2]