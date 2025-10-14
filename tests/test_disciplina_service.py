# tests/test_disciplina_service.py

import pytest
from sqlalchemy import select
from backend.services.disciplina_service import DisciplinaService
from backend.models.database import db
from backend.models.disciplina import Disciplina
from backend.models.historico_disciplina import HistoricoDisciplina
from backend.models.disciplina_turma import DisciplinaTurma
from backend.models.aluno import Aluno
from backend.models.turma import Turma

class TestDisciplinaService:
    """
    Suíte de testes para o DisciplinaService.
    """

    def test_create_disciplina_and_associates_with_existing_students(self, db_session, setup_school_with_users):
        """
        Testa se ao criar uma nova disciplina, ela é automaticamente associada
        a todos os alunos já existentes na escola.
        """
        school, admin_user, alunos = setup_school_with_users

        disciplina_data = {
            'materia': 'Ordem Unida',
            'carga_horaria_prevista': 30,
            'ciclo': 1
        }

        # Ação
        success, message = DisciplinaService.create_disciplina(disciplina_data, school.id)

        # Asserções
        assert success is True
        assert "associada aos alunos da escola" in message

        # Verifica se a disciplina foi criada
        disciplina_criada = db_session.scalar(select(Disciplina).filter_by(materia='Ordem Unida'))
        assert disciplina_criada is not None
        assert disciplina_criada.school_id == school.id

        # Verifica se todos os alunos da escola foram matriculados na nova disciplina
        total_alunos_escola = db_session.scalar(
            select(db.func.count(Aluno.id)).join(Turma).where(Turma.school_id == school.id)
        )
        total_matriculas = db_session.scalar(
            select(db.func.count(HistoricoDisciplina.id)).where(HistoricoDisciplina.disciplina_id == disciplina_criada.id)
        )
        assert total_matriculas == total_alunos_escola
        assert total_alunos_escola == len(alunos)


    def test_update_disciplina(self, db_session, setup_school_with_users):
        """
        Testa a atualização dos dados de uma disciplina existente.
        """
        school, _, _ = setup_school_with_users
        
        # Cria uma disciplina inicial
        disciplina = Disciplina(materia="Tiro Defensivo", carga_horaria_prevista=40, ciclo=1, school_id=school.id)
        db_session.add(disciplina)
        db_session.commit()

        update_data = {
            'materia': 'Tiro Policial',
            'carga_horaria_prevista': 50,
            'ciclo': 2
        }

        # Ação
        success, message = DisciplinaService.update_disciplina(disciplina.id, update_data)

        # Asserções
        assert success is True
        assert message == "Disciplina atualizada com sucesso!"
        db_session.refresh(disciplina)
        assert disciplina.materia == 'Tiro Policial'
        assert disciplina.carga_horaria_prevista == 50
        assert disciplina.ciclo == 2

    def test_delete_disciplina_cascades(self, db_session, setup_school_with_users):
        """
        Testa se ao deletar uma disciplina, todos os seus vínculos
        (HistoricoDisciplina, DisciplinaTurma) são removidos em cascata.
        """
        school, _, alunos = setup_school_with_users
        aluno1, aluno2 = alunos

        # Cria a disciplina e as associações
        disciplina = Disciplina(materia="Defesa Pessoal", carga_horaria_prevista=25, ciclo=1, school_id=school.id)
        db_session.add(disciplina)
        db_session.commit()
        disciplina_id = disciplina.id

        matricula1 = HistoricoDisciplina(aluno_id=aluno1.id, disciplina_id=disciplina_id)
        vinculo_turma = DisciplinaTurma(pelotao=aluno1.turma.nome, disciplina_id=disciplina_id)
        db_session.add_all([matricula1, vinculo_turma])
        db_session.commit()

        # Verifica se as associações existem antes de deletar
        assert db_session.get(HistoricoDisciplina, matricula1.id) is not None
        assert db_session.get(DisciplinaTurma, vinculo_turma.id) is not None

        # Ação
        success, message = DisciplinaService.delete_disciplina(disciplina_id)

        # Asserções
        assert success is True
        assert "registros associados foram excluídos" in message
        assert db_session.get(Disciplina, disciplina_id) is None
        assert db_session.get(HistoricoDisciplina, matricula1.id) is None
        assert db_session.get(DisciplinaTurma, vinculo_turma.id) is None

    def test_get_disciplinas_agrupadas_por_ciclo(self, db_session, setup_school_with_users):
        """
        Testa se a função agrupa e retorna as disciplinas por ciclo corretamente.
        """
        school, _, _ = setup_school_with_users
        
        # Cria disciplinas em ciclos diferentes
        d1_c1 = Disciplina(materia="Legislação I", carga_horaria_prevista=20, ciclo=1, school_id=school.id)
        d2_c1 = Disciplina(materia="Armamento e Munição", carga_horaria_prevista=30, ciclo=1, school_id=school.id)
        d1_c2 = Disciplina(materia="Legislação II", carga_horaria_prevista=20, ciclo=2, school_id=school.id)
        db_session.add_all([d1_c1, d2_c1, d1_c2])
        db_session.commit()

        # Ação
        disciplinas_agrupadas = DisciplinaService.get_disciplinas_agrupadas_por_ciclo(school.id)

        # Asserções
        assert 1 in disciplinas_agrupadas
        assert 2 in disciplinas_agrupadas
        assert 3 not in disciplinas_agrupadas
        assert len(disciplinas_agrupadas[1]) == 2
        assert len(disciplinas_agrupadas[2]) == 1
        assert disciplinas_agrupadas[1][0].materia == "Armamento e Munição" # Ordenado alfabeticamente
        assert disciplinas_agrupadas[1][1].materia == "Legislação I"