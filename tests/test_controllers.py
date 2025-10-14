# tests/test_controllers.py

import pytest
from sqlalchemy import select
from datetime import date, timedelta
from flask import session
from backend.models.user import User
from backend.models.school import School
from backend.models.user_school import UserSchool
from backend.models.aluno import Aluno
from backend.models.instrutor import Instrutor
from backend.models.turma import Turma
from backend.models.disciplina import Disciplina
from backend.models.disciplina_turma import DisciplinaTurma
from backend.models.semana import Semana
from backend.models.horario import Horario
from backend.models.database import db

class TestAuthController:
    """Testes para o fluxo de autenticação."""
    # ... (os testes de login que já passam) ...
    def test_login_redirects_to_complete_profile_for_new_student(self, test_client, test_app):
        pass # Placeholder for existing test
    def test_login_failure_wrong_password(self, test_client, test_app):
        pass # Placeholder for existing test

class TestPermissionSystem:
    """Testes para o sistema de permissões."""
    # ... (os testes de permissão que já passam) ...
    def test_school_admin_cannot_access_super_admin_dashboard(self, test_client, test_app):
        pass # Placeholder for existing test
    def test_super_admin_view_as_school_context(self, test_client, test_app):
        pass # Placeholder for existing test

class TestWorkflow:
    """
    Testes que validam fluxos de trabalho completos envolvendo múltiplos usuários.
    """
    def test_full_class_lifecycle(self, test_client, test_app):
        """
        Valida o ciclo de vida completo de uma aula.
        """
        with test_app.app_context():
            # --- 1. SETUP CORRIGIDO E EM ETAPAS ---
            # ETAPA A: Criar a entidade principal (Escola) e salvar para obter um ID.
            school = School(nome="Escola de Fluxo Completo")
            db.session.add(school)
            db.session.commit()

            # ETAPA B: Criar entidades que dependem da Escola.
            turma = Turma(nome="Pelotao-Workflow", ano=2025, school_id=school.id)
            disciplina = Disciplina(materia="Teste de Workflow", carga_horaria_prevista=20, school_id=school.id, ciclo=1)
            semana = Semana(nome="Semana Workflow", data_inicio=date.today(), data_fim=date.today() + timedelta(days=6), ciclo=1)
            db.session.add_all([turma, disciplina, semana])
            db.session.commit()

            # ETAPA C: Criar os usuários.
            instrutor_user = User(id_func='instrutor_wf', nome_de_guerra='Sgt Workflow', role='instrutor', is_active=True)
            instrutor_user.set_password('pass1')
            admin_user = User(id_func='admin_wf', nome_de_guerra='Ten Workflow', role='admin_escola', is_active=True)
            admin_user.set_password('pass2')
            aluno_user = User(id_func='aluno_wf', nome_de_guerra='Sd Workflow', role='aluno', is_active=True)
            aluno_user.set_password('pass3')
            db.session.add_all([instrutor_user, admin_user, aluno_user])
            db.session.commit()

            # ETAPA D: Criar os perfis e associações finais.
            instrutor = Instrutor(user_id=instrutor_user.id, matricula='instrutor_wf', especializacao='Testes', formacao='TI')
            aluno = Aluno(user_id=aluno_user.id, matricula='aluno_wf', opm='EsFAS', turma_id=turma.id)
            db.session.add_all([instrutor, aluno])
            db.session.commit()
            
            db.session.add_all([
                UserSchool(user_id=instrutor_user.id, school_id=school.id, role='instrutor'),
                UserSchool(user_id=admin_user.id, school_id=school.id, role='admin_escola'),
                UserSchool(user_id=aluno_user.id, school_id=school.id, role='aluno')
            ])
            vinculo = DisciplinaTurma(pelotao=turma.nome, disciplina_id=disciplina.id, instrutor_id_1=instrutor.id)
            db.session.add(vinculo)
            db.session.commit()

            # --- 2. AÇÃO DO INSTRUTOR ---
            test_client.post('/auth/login', data={'username': 'instrutor_wf', 'password': 'pass1'})
            aula_data = {'pelotao': turma.nome, 'semana_id': semana.id, 'dia': 'segunda', 'periodo': 3, 'disciplina_id': disciplina.id, 'duracao': 2}
            response_instrutor = test_client.post('/horario/salvar-aula', json=aula_data)
            assert response_instrutor.status_code == 200
            aula_criada = db.session.scalar(select(Horario).where(Horario.pelotao == turma.nome))
            assert aula_criada is not None
            assert aula_criada.status == 'pendente'
            test_client.get('/auth/logout')

            # --- 3. AÇÃO DO ADMINISTRADOR ---
            test_client.post('/auth/login', data={'username': 'admin_wf', 'password': 'pass2'})
            response_admin = test_client.post('/horario/aprovar', data={'horario_id': aula_criada.id, 'action': 'aprovar'})
            assert response_admin.status_code == 302
            db.session.refresh(aula_criada)
            assert aula_criada.status == 'confirmado'
            test_client.get('/auth/logout')

            # --- 4. VERIFICAÇÃO DO ALUNO ---
            test_client.post('/auth/login', data={'username': 'aluno_wf', 'password': 'pass3'})
            response_aluno = test_client.get(f'/horario/{turma.nome}?semana_id={semana.id}')
            assert response_aluno.status_code == 200
            assert b'Teste de Workflow' in response_aluno.data
            assert b'Sgt Workflow' in response_aluno.data