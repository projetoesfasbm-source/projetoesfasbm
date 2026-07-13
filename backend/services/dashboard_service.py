# backend/services/dashboard_service.py

from sqlalchemy import select, func, and_
from cachetools import TTLCache
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
from ..models.semana import Semana
from ..models.ciclo import Ciclo

class DashboardService:
    _counts_cache = TTLCache(maxsize=50, ttl=30)

    @staticmethod
    def get_dashboard_data(school_id=None, edicao_id=None):
        cache_key = (school_id, edicao_id)
        cached_counts = DashboardService._counts_cache.get(cache_key)

        if cached_counts:
            total_alunos, total_instrutores, total_disciplinas, total_aulas_pendentes, total_processos_pendentes = cached_counts
        else:
            # --- Contagens Básicas ---
            alunos_query = select(func.count(Aluno.id)).join(User, Aluno.user_id == User.id).where(User.is_active == True)
            if school_id:
                alunos_query = alunos_query.join(Turma, Aluno.turma_id == Turma.id).where(Turma.school_id == school_id)
            if edicao_id:
                alunos_query = alunos_query.where(Turma.edicao_id == edicao_id)
            total_alunos = db.session.scalar(alunos_query) or 0

            # Instrutores são filtrados diretamente pela escola a qual pertencem
            instrutores_query = select(func.count(Instrutor.id)).join(User, Instrutor.user_id == User.id).where(User.is_active == True)
            if school_id:
                instrutores_query = instrutores_query.where(Instrutor.school_id == school_id)
            total_instrutores = db.session.scalar(instrutores_query) or 0

            disciplinas_query = select(func.count(func.distinct(Disciplina.materia)))
            if school_id:
                disciplinas_query = disciplinas_query.join(Turma).where(Turma.school_id == school_id)
            total_disciplinas = db.session.scalar(disciplinas_query) or 0

            # --- AULAS PENDENTES (Para SENS) ---
            aulas_pendentes_query = select(func.count(Horario.id)).where(Horario.status == 'pendente')
            if school_id or edicao_id:
                aulas_pendentes_query = aulas_pendentes_query.join(Semana).join(Ciclo)
                if school_id:
                    aulas_pendentes_query = aulas_pendentes_query.where(Ciclo.school_id == school_id)
                if edicao_id:
                    aulas_pendentes_query = aulas_pendentes_query.where(Ciclo.edicao_id == edicao_id)

            total_aulas_pendentes = db.session.scalar(aulas_pendentes_query) or 0

            # --- PROCESSOS PENDENTES (Para CAL) ---
            processos_pendentes_query = select(func.count(ProcessoDisciplina.id)).where(ProcessoDisciplina.status != 'Finalizado')
            if school_id or edicao_id:
                processos_pendentes_query = processos_pendentes_query.join(ProcessoDisciplina.aluno).join(Turma, Aluno.turma_id == Turma.id)
                if school_id:
                    processos_pendentes_query = processos_pendentes_query.where(Turma.school_id == school_id)
                if edicao_id:
                    processos_pendentes_query = processos_pendentes_query.where(Turma.edicao_id == edicao_id)

            total_processos_pendentes = db.session.scalar(processos_pendentes_query) or 0

            DashboardService._counts_cache[cache_key] = (
                total_alunos, total_instrutores, total_disciplinas,
                total_aulas_pendentes, total_processos_pendentes
            )

        lista_aulas_pendentes = []
        lista_processos_pendentes = []

        # --- Listas Padrão ---
        usuarios_recentes_query = select(User).join(UserSchool).where(User.is_active == True).order_by(User.id.desc()).limit(5)
        if school_id:
            usuarios_recentes_query = usuarios_recentes_query.where(UserSchool.school_id == school_id)
        usuarios_recentes = db.session.scalars(usuarios_recentes_query).unique().all()

        proximas_aulas_query = select(Horario).join(Semana).join(Ciclo).order_by(Horario.id.desc()).limit(5)
        if school_id:
            proximas_aulas_query = proximas_aulas_query.where(Ciclo.school_id == school_id)
        if edicao_id: # <--- FILTRO DE EDIÇÃO ADICIONADO
            proximas_aulas_query = proximas_aulas_query.where(Ciclo.edicao_id == edicao_id)
            
        proximas_aulas = db.session.scalars(proximas_aulas_query).all()

        return {
            'total_alunos': total_alunos,
            'total_instrutores': total_instrutores,
            'total_disciplinas': total_disciplinas,
            'aulas_pendentes': total_aulas_pendentes,
            'lista_aulas_pendentes': lista_aulas_pendentes,
            'lista_processos_pendentes': lista_processos_pendentes,
            'usuarios_recentes': usuarios_recentes,
            'proximas_aulas': proximas_aulas
        }
