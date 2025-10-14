# tests/test_vinculo_service.py

import pytest
from backend.services.vinculo_service import VinculoService
from backend.models.database import db
from backend.models.user import User
from backend.models.instrutor import Instrutor
from backend.models.disciplina import Disciplina
from backend.models.turma import Turma
from backend.models.school import School
from backend.models.disciplina_turma import DisciplinaTurma

@pytest.fixture
def setup_data(db_session):
    """Cria dados iniciais para os testes de vínculo."""
    school = School(nome="Escola Teste")
    db_session.add(school)
    db_session.commit()

    user_instrutor = User(username='instrutor', id_func='inst1', email='instrutor@test.com')
    user_instrutor.set_password('password')
    db_session.add(user_instrutor)
    db_session.commit()

    instrutor = Instrutor(
        user_id=user_instrutor.id,
        matricula="123456",
        especializacao="Teste",
        formacao="Engenharia de Testes"
    )
    db_session.add(instrutor)
    db_session.commit()

    turma = Turma(nome="Turma A", ano=2023, school_id=school.id)
    db_session.add(turma)
    db_session.commit()

    disciplina = Disciplina(
        materia="Teste de Software",
        carga_horaria_prevista=60,
        school_id=school.id
    )
    db_session.add(disciplina)
    db_session.commit()

    return instrutor, turma, disciplina

class TestVinculoService:
    """Suíte de testes para o VinculoService."""

    def test_add_vinculo_success(self, db_session, setup_data):
        """Testa a criação de um novo vínculo com sucesso."""
        instrutor, turma, disciplina = setup_data
        
        success, message = VinculoService.add_vinculo(instrutor.id, turma.id, disciplina.id)

        assert success is True
        assert message == 'Vínculo criado com sucesso!'
        vinculo = db.session.query(DisciplinaTurma).filter_by(instrutor_id_1=instrutor.id).one()
        assert vinculo.pelotao == turma.nome
        assert vinculo.disciplina_id == disciplina.id

    def test_add_vinculo_updates_existing(self, db_session, setup_data):
        """Testa se um vínculo existente é atualizado ao invés de criar um novo."""
        instrutor, turma, disciplina = setup_data
        
        # Cria um vínculo inicial sem instrutor
        vinculo_inicial = DisciplinaTurma(pelotao=turma.nome, disciplina_id=disciplina.id)
        db_session.add(vinculo_inicial)
        db_session.commit()

        success, message = VinculoService.add_vinculo(instrutor.id, turma.id, disciplina.id)

        assert success is True
        assert 'Vínculo atualizado com sucesso' in message
        assert vinculo_inicial.instrutor_id_1 == instrutor.id

    def test_edit_vinculo_success(self, db_session, setup_data):
        """Testa a edição de um vínculo com sucesso."""
        instrutor, turma, disciplina = setup_data
        vinculo = DisciplinaTurma(instrutor_id_1=instrutor.id, pelotao=turma.nome, disciplina_id=disciplina.id)
        db_session.add(vinculo)
        db_session.commit()

        # Novos dados para edição
        user_novo_instrutor = User(username='instrutor2', id_func='inst2', email='instrutor2@test.com')
        db_session.add(user_novo_instrutor)
        db_session.commit()
        novo_instrutor = Instrutor(
            user_id=user_novo_instrutor.id,
            matricula="654321",
            especializacao="Nova",
            formacao="Nova Engenharia"
        )
        db_session.add(novo_instrutor)
        db_session.commit()
        db_session.add(novo_instrutor)
        db_session.commit()

        success, message = VinculoService.edit_vinculo(vinculo.id, novo_instrutor.id, turma.id, disciplina.id)

        assert success is True
        assert message == 'Vínculo atualizado com sucesso!'
        assert vinculo.instrutor_id_1 == novo_instrutor.id

    def test_delete_vinculo_success(self, db_session, setup_data):
        """Testa a exclusão de um vínculo com sucesso."""
        instrutor, turma, disciplina = setup_data
        vinculo = DisciplinaTurma(instrutor_id_1=instrutor.id, pelotao=turma.nome, disciplina_id=disciplina.id)
        db_session.add(vinculo)
        db_session.commit()
        vinculo_id = vinculo.id

        success, message = VinculoService.delete_vinculo(vinculo_id)

        assert success is True
        assert message == 'Vínculo excluído com sucesso!'
        assert db_session.get(DisciplinaTurma, vinculo_id) is None

    def test_get_all_vinculos(self, db_session, setup_data):
        """Testa se a listagem de vínculos funciona corretamente."""
        instrutor, turma, disciplina = setup_data
        vinculo = DisciplinaTurma(instrutor_id_1=instrutor.id, pelotao=turma.nome, disciplina_id=disciplina.id)
        db_session.add(vinculo)
        db_session.commit()

        vinculos = VinculoService.get_all_vinculos()
        assert len(vinculos) == 1
        assert vinculos[0].id == vinculo.id

    def test_get_vinculos_with_filters(self, db_session, setup_data):
        """Testa a listagem de vínculos com filtros."""
        instrutor, turma, disciplina = setup_data
        vinculo = DisciplinaTurma(instrutor_id_1=instrutor.id, pelotao=turma.nome, disciplina_id=disciplina.id)
        db_session.add(vinculo)
        db_session.commit()

        # Testa filtro por turma
        vinculos_turma = VinculoService.get_all_vinculos(turma_filtrada=turma.nome)
        assert len(vinculos_turma) == 1
        
        # Testa filtro por disciplina
        vinculos_disciplina = VinculoService.get_all_vinculos(disciplina_filtrada_id=disciplina.id)
        assert len(vinculos_disciplina) == 1

        # Testa filtro combinado
        vinculos_combinado = VinculoService.get_all_vinculos(turma_filtrada=turma.nome, disciplina_filtrada_id=disciplina.id)
        assert len(vinculos_combinado) == 1

        # Testa filtro que não retorna nada
        vinculos_vazio = VinculoService.get_all_vinculos(turma_filtrada="Turma Inexistente")
        assert len(vinculos_vazio) == 0
