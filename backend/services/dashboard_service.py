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

class DashboardService:
    @staticmethod
    def get_dashboard_data(school_id=None):
        
        # --- Contagens Básicas ---
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

        # --- AULAS PENDENTES (Para SENS) ---
        aulas_pendentes_query = select(Horario).where(Horario.status == 'pendente')
        if school_id:
            aulas_pendentes_query = aulas_pendentes_query.join(Turma, Horario.pelotao == Turma.nome).where(Turma.school_id == school_id)
        
        lista_aulas_pendentes = db.session.scalars(aulas_pendentes_query).all()
        # CORREÇÃO: Calcula o total para evitar o erro no template
        total_aulas_pendentes = len(lista_aulas_pendentes)

        # --- PROCESSOS PENDENTES (Para CAL) ---
        processos_pendentes_query = select(ProcessoDisciplina).where(ProcessoDisciplina.status != 'Finalizado')
        if school_id:
            processos_pendentes_query = processos_pendentes_query.join(Aluno).join(User, Aluno.user_id == User.id).join(UserSchool, User.id == UserSchool.user_id).where(UserSchool.school_id == school_id)
        lista_processos_pendentes = db.session.scalars(processos_pendentes_query).all()

        # --- Listas Padrão ---
        usuarios_recentes_query = select(User).join(UserSchool).where(User.is_active == True).order_by(User.id.desc()).limit(5)
        if school_id:
            usuarios_recentes_query = usuarios_recentes_query.where(UserSchool.school_id == school_id)
        usuarios_recentes = db.session.scalars(usuarios_recentes_query).unique().all()
        
        proximas_aulas_query = select(Horario).join(Turma, Horario.pelotao == Turma.nome).order_by(Horario.id.desc()).limit(5)
        if school_id:
            proximas_aulas_query = proximas_aulas_query.where(Turma.school_id == school_id)
        proximas_aulas = db.session.scalars(proximas_aulas_query).all()

        return {
            'total_alunos': total_alunos,
            'total_instrutores': total_instrutores,
            'total_disciplinas': total_disciplinas,
            # CORREÇÃO: Envia tanto o número (para o Admin) quanto a lista (para o SENS)
            'aulas_pendentes': total_aulas_pendentes, 
            'lista_aulas_pendentes': lista_aulas_pendentes,
            'lista_processos_pendentes': lista_processos_pendentes,
            'usuarios_recentes': usuarios_recentes,
            'proximas_aulas': proximas_aulas
        }