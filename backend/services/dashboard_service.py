# backend/services/dashboard_service.py

from sqlalchemy import select, func
from ..models.database import db
from ..models.user import User
from ..models.aluno import Aluno
from ..models.instrutor import Instrutor
from ..models.disciplina import Disciplina
from ..models.turma import Turma
from ..models.school import School
from ..models.user_school import UserSchool
from ..models.horario import Horario # <-- NOVA IMPORTAÇÃO

class DashboardService:
    @staticmethod
    def get_dashboard_data(school_id=None):
        """
        Coleta dados agregados para o dashboard, como contagens de
        alunos, instrutores, disciplinas e aulas pendentes, 
        filtrando por escola se um school_id for fornecido.
        """
        
        # --- Contagem de Alunos ---
        alunos_query = (
            select(func.count(Aluno.id))
            .join(User, Aluno.user_id == User.id)
            .where(User.is_active == True)
        )
        if school_id:
            alunos_query = alunos_query.join(UserSchool, UserSchool.user_id == User.id).where(UserSchool.school_id == school_id)

        total_alunos = db.session.scalar(alunos_query) or 0
        
        # --- Contagem de Instrutores ---
        instrutores_query = (
            select(func.count(Instrutor.id))
            .join(User, Instrutor.user_id == User.id)
            .where(User.is_active == True)
        )
        if school_id:
            instrutores_query = instrutores_query.join(UserSchool, UserSchool.user_id == User.id).where(UserSchool.school_id == school_id)
            
        total_instrutores = db.session.scalar(instrutores_query) or 0
        
        # --- Lógica de Contagem de Disciplinas Corrigida ---
        disciplinas_query = select(func.count(Disciplina.id))
        if school_id:
            disciplinas_query = disciplinas_query.join(Turma).where(Turma.school_id == school_id)
            
        total_disciplinas = db.session.scalar(disciplinas_query) or 0

        # --- Contagem de Turmas ---
        turmas_query = select(func.count(Turma.id))
        if school_id:
            turmas_query = turmas_query.where(Turma.school_id == school_id)
        
        total_turmas = db.session.scalar(turmas_query) or 0
        
        # --- NOVA LÓGICA: Contagem de Aulas Pendentes ---
        aulas_pendentes_query = select(func.count(Horario.id)).where(Horario.status == 'pendente')
        if school_id:
            # Filtra as aulas pendentes para a escola atual, juntando através das disciplinas e turmas
            aulas_pendentes_query = aulas_pendentes_query.join(Disciplina).join(Turma).where(Turma.school_id == school_id)

        total_aulas_pendentes = db.session.scalar(aulas_pendentes_query) or 0
        
        # Retorna os dados para o controller
        return {
            'total_alunos': total_alunos,
            'total_instrutores': total_instrutores,
            'total_disciplinas': total_disciplinas,
            'total_turmas': total_turmas,
            'aulas_pendentes': total_aulas_pendentes, # <-- DADO RESTAURADO
        }