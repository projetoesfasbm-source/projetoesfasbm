# backend/services/relatorio_service.py

from sqlalchemy import func, or_, and_, case, distinct
from backend.models.database import db
from backend.models.aluno import Aluno
from backend.models.turma import Turma
from backend.models.disciplina import Disciplina
from backend.models.horario import Horario
from backend.models.instrutor import Instrutor
from backend.models.semana import Semana
from datetime import datetime, date

class RelatorioService:
    
    @staticmethod
    def get_resumo_turma(turma_id):
        """
        Gera um resumo da turma com contagem de alunos e status.
        """
        turma = db.session.get(Turma, turma_id)
        if not turma:
            return None
            
        total_alunos = db.session.query(func.count(Aluno.id)).filter_by(turma_id=turma_id).scalar()
        
        return {
            "turma": turma,
            "total_alunos": total_alunos
        }

    @staticmethod
    def calcular_horas_disciplina_real(disciplina_id):
        """
        Calcula a carga horária TOTAL executada pela DISCIPLINA.
        Soma a duração dos horários únicos (confirmados e passados).
        """
        query = db.session.query(func.sum(Horario.duracao)).join(Semana).filter(
            Horario.disciplina_id == disciplina_id,
            Semana.data_inicio <= datetime.now().date(),
            Horario.status == 'confirmado'
        )
        
        total = query.scalar() or 0
        return float(total)

    @staticmethod
    def get_relatorio_disciplinas(turma_id):
        """
        Retorna dados consolidados das disciplinas da turma para relatórios.
        """
        disciplinas = db.session.query(Disciplina).filter_by(turma_id=turma_id).all()
        
        relatorio = []
        
        for disciplina in disciplinas:
            # 1. Carga Horária Prevista
            ch_prevista = disciplina.carga_horaria_prevista if disciplina.carga_horaria_prevista else 0
            
            # 2. Carga Horária Executada (Real - sem duplicar por instrutor)
            ch_executada = RelatorioService.calcular_horas_disciplina_real(disciplina.id)
                
            # Calcular percentual
            percentual = (ch_executada / ch_prevista * 100) if ch_prevista > 0 else 0
            
            # 3. Listar Instrutores envolvidos
            q_instr1 = db.session.query(Horario.instrutor_id).filter(Horario.disciplina_id == disciplina.id).distinct()
            q_instr2 = db.session.query(Horario.instrutor_id_2).filter(Horario.disciplina_id == disciplina.id).filter(Horario.instrutor_id_2.isnot(None)).distinct()
            
            ids_instrutores = set()
            for r in q_instr1: 
                if r[0]: ids_instrutores.add(r[0])
            for r in q_instr2: 
                if r[0]: ids_instrutores.add(r[0])
            
            nomes_instrutores = []
            if ids_instrutores:
                instrutores = db.session.query(Instrutor).filter(Instrutor.id.in_(ids_instrutores)).all()
                # Usa nome_guerra que é garantido
                nomes_instrutores = [i.nome_guerra for i in instrutores if i.nome_guerra]

            relatorio.append({
                "disciplina_nome": disciplina.materia,
                "ch_prevista": ch_prevista,
                "ch_executada": float(ch_executada),
                "percentual": round(percentual, 1),
                "instrutores": ", ".join(nomes_instrutores)
            })
            
        return relatorio

    @staticmethod
    def get_horas_aula_por_instrutor(data_inicio, data_fim, is_rr=None, instrutor_ids=None):
        """
        Gera relatório de horas por instrutor em um período.
        Aceita filtros e corrige erro de atributo.
        """
        # 1. Base da query: Instrutores
        query = db.session.query(Instrutor)

        # 2. Aplicar filtro is_rr
        if is_rr is not None:
            if isinstance(is_rr, str):
                if is_rr.lower() == 'true':
                    query = query.filter(Instrutor.is_rr == True)
                elif is_rr.lower() == 'false':
                    query = query.filter(Instrutor.is_rr == False)
            else:
                query = query.filter(Instrutor.is_rr == bool(is_rr))

        # 3. Aplicar filtro de IDs
        if instrutor_ids:
            if not isinstance(instrutor_ids, list):
                instrutor_ids = [instrutor_ids]
            query = query.filter(Instrutor.id.in_(instrutor_ids))
        
        instrutores = query.all()
        dados = []

        # 4. Iterar e calcular horas
        for instr in instrutores:
            # Soma horas como TITULAR
            horas_titular = db.session.query(func.sum(Horario.duracao))\
                .join(Semana)\
                .filter(
                    Horario.instrutor_id == instr.id,
                    Semana.data_inicio >= data_inicio,
                    Semana.data_fim <= data_fim,
                    Horario.status == 'confirmado'
                ).scalar() or 0

            # Soma horas como ADJUNTO
            horas_adjunto = db.session.query(func.sum(Horario.duracao))\
                .join(Semana)\
                .filter(
                    Horario.instrutor_id_2 == instr.id,
                    Semana.data_inicio >= data_inicio,
                    Semana.data_fim <= data_fim,
                    Horario.status == 'confirmado'
                ).scalar() or 0

            total_horas = float(horas_titular) + float(horas_adjunto)

            if total_horas > 0:
                # CORREÇÃO: Tenta pegar nome_completo, se falhar usa nome_guerra
                nome_exibicao = getattr(instr, 'nome_completo', None)
                if not nome_exibicao:
                    # Tenta acessar via relacionamento 'user' se existir
                    if hasattr(instr, 'user') and instr.user:
                        nome_exibicao = getattr(instr.user, 'nome_completo', instr.nome_guerra)
                    else:
                        nome_exibicao = instr.nome_guerra

                dados.append({
                    'nome': nome_exibicao,
                    'posto': instr.posto_graduacao or 'Instrutor',
                    'horas': total_horas,
                    'tipo': 'RR' if instr.is_rr else 'Ativa'
                })
        
        # Ordenar por nome
        dados.sort(key=lambda x: x['nome'])
        
        return dados