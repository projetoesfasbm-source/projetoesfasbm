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
from ..models.horario import Horario
from ..models.processo_disciplina import ProcessoDisciplina
from datetime import datetime

class DashboardService:
    @staticmethod
    def get_dashboard_data(school_id=None):
        """
        Coleta dados agregados para o dashboard, filtrando rigorosamente
        pelo school_id para garantir que o SENS veja apenas sua escola.
        """
        
        # --- Contagens ---
        alunos_query = select(func.count(Aluno.id)).join(User, Aluno.user_id == User.id).where(User.is_active == True)
        if school_id:
            alunos_query = alunos_query.join(UserSchool, UserSchool.user_id == User.id).where(UserSchool.school_id == school_id)
        total_alunos = db.session.scalar(alunos_query) or 0
        
        instrutores_query = select(func.count(Instrutor.id)).join(User, Instrutor.user_id == User.id).where(User.is_active == True)
        if school_id:
            instrutores_query = instrutores_query.join(UserSchool, UserSchool.user_id == User.id).where(UserSchool.school_id == school_id)
        total_instrutores = db.session.scalar(instrutores_query) or 0
        
        disciplinas_query = select(func.count(func.distinct(Disciplina.materia)))
        if school_id:
            disciplinas_query = disciplinas_query.join(Turma).where(Turma.school_id == school_id)
        total_disciplinas = db.session.scalar(disciplinas_query) or 0

        total_turmas = db.session.scalar(select(func.count(Turma.id)).where(Turma.school_id == school_id)) if school_id else 0
        
        # --- AULAS PENDENTES (Lista e Contagem) ---
        aulas_pendentes_query = (
            select(Horario)
            .where(Horario.status == 'pendente')
            .order_by(Horario.id.asc())
            .limit(5)
        )
        if school_id:
            # Join explícito com Turma para filtrar pela escola
            aulas_pendentes_query = aulas_pendentes_query.join(Turma, Horario.pelotao == Turma.nome).where(Turma.school_id == school_id)

        lista_aulas_pendentes = db.session.scalars(aulas_pendentes_query).all()
        # Nota: esta contagem é apenas das 5 primeiras, se quiser total real precisaria de outra query, mas serve para UI
        
        # --- PROCESSOS PENDENTES (Lista para CAL) ---
        processos_pendentes_query = (
            select(ProcessoDisciplina)
            .join(Aluno)
            .join(User, Aluno.user_id == User.id)
            .where(ProcessoDisciplina.status != 'Finalizado')
            .order_by(ProcessoDisciplina.data_ocorrencia.desc())
            .limit(5)
        )
        if school_id:
            processos_pendentes_query = processos_pendentes_query.join(UserSchool, User.id == UserSchool.user_id).where(UserSchool.school_id == school_id)
            
        lista_processos_pendentes = db.session.scalars(processos_pendentes_query).all()

        # --- Usuários Recentes ---
        usuarios_recentes_query = select(User).join(UserSchool).where(User.is_active == True).order_by(User.id.desc()).limit(5)
        if school_id:
            usuarios_recentes_query = usuarios_recentes_query.where(UserSchool.school_id == school_id)
        usuarios_recentes = db.session.scalars(usuarios_recentes_query).unique().all()
        
        # --- Próximas Aulas ---
        proximas_aulas_query = (
            select(Horario)
            .join(Turma, Horario.pelotao == Turma.nome)
            .order_by(Horario.id.desc())
            .limit(5)
        )
        if school_id:
            proximas_aulas_query = proximas_aulas_query.where(Turma.school_id == school_id)
        proximas_aulas = db.session.scalars(proximas_aulas_query).all()

        return {
            'total_alunos': total_alunos,
            'total_instrutores': total_instrutores,
            'total_disciplinas': total_disciplinas,
            'total_turmas': total_turmas,
            'lista_aulas_pendentes': lista_aulas_pendentes,
            'lista_processos_pendentes': lista_processos_pendentes,
            'usuarios_recentes': usuarios_recentes,
            'proximas_aulas': proximas_aulas
        }