# backend/services/disciplina_service.py

from collections import defaultdict
from sqlalchemy import select, func, and_, or_
from sqlalchemy.exc import IntegrityError
from flask import current_app
from datetime import date, timedelta

from ..models.database import db
from ..models.disciplina import Disciplina
from ..models.disciplina_turma import DisciplinaTurma
from ..models.historico_disciplina import HistoricoDisciplina
from ..models.aluno import Aluno
from ..models.turma import Turma
from ..models.ciclo import Ciclo
from ..models.horario import Horario
from ..models.semana import Semana
from ..models.diario_classe import DiarioClasse

class DisciplinaService:
    
    # --- MÉTODOS DE CONSULTA ---

    @staticmethod
    def get_all_disciplinas():
        """Retorna todas as disciplinas cadastradas no sistema."""
        return db.session.scalars(select(Disciplina).order_by(Disciplina.materia)).all()

    @staticmethod
    def get_disciplinas_by_turma(turma_id):
        """Retorna disciplinas de uma turma específica."""
        return db.session.scalars(
            select(Disciplina)
            .where(Disciplina.turma_id == turma_id)
            .order_by(Disciplina.materia)
        ).all()

    @staticmethod
    def get_disciplinas_by_school(school_id):
        """
        Busca todas as disciplinas pertencentes a uma escola específica.
        """
        if not school_id:
            return []
            
        stmt = (
            select(Disciplina)
            .join(Turma, Disciplina.turma_id == Turma.id)
            .where(Turma.school_id == school_id)
            .order_by(Turma.nome, Disciplina.materia)
        )
        return db.session.scalars(stmt).all()

    @staticmethod
    def get_by_id(id: int):
        """Busca disciplina por ID."""
        return db.session.get(Disciplina, id)

    # --- MÉTODOS DE ESCRITA (CRUD) ---

    @staticmethod
    def create_disciplina(data, school_id):
        materia = data.get('materia')
        carga_horaria = data.get('carga_horaria_prevista')
        ciclo_id = data.get('ciclo_id')
        carga_cumprida = data.get('carga_horaria_cumprida', 0)
        turma_ids = data.get('turma_ids', [])

        if not all([materia, carga_horaria, ciclo_id, turma_ids]):
            return False, 'Matéria, Carga Horária, Ciclo e pelo menos uma Turma são obrigatórios.'

        success_count = 0
        errors = []

        for turma_id in turma_ids:
            try:
                turma = db.session.get(Turma, int(turma_id))
                if not turma or turma.school_id != school_id:
                    errors.append(f'Turma com ID {turma_id} é inválida ou não pertence à sua escola.')
                    continue

                exists = db.session.execute(
                    select(Disciplina).where(Disciplina.materia == materia, Disciplina.turma_id == turma_id)
                ).scalar_one_or_none()
                
                if exists:
                    errors.append(f'A disciplina "{materia}" já existe na turma {turma.nome}.')
                    continue

                nova_disciplina = Disciplina(
                    materia=materia,
                    carga_horaria_prevista=int(carga_horaria),
                    carga_horaria_cumprida=int(carga_cumprida or 0),
                    ciclo_id=int(ciclo_id),
                    turma_id=int(turma_id)
                )
                db.session.add(nova_disciplina)
                db.session.flush()

                if turma.alunos:
                    for aluno in turma.alunos:
                        matricula = HistoricoDisciplina(aluno_id=aluno.id, disciplina_id=nova_disciplina.id)
                        db.session.add(matricula)
                
                success_count += 1
            except Exception as e:
                db.session.rollback()
                errors.append(f'Erro na turma {turma_id}: {str(e)}')
                db.session.begin()

        if success_count > 0:
            db.session.commit()
        
        message = f'{success_count} disciplina(s) criada(s). '
        if errors:
            message += "Erros: " + "; ".join(errors)
        
        return success_count > 0, message

    @staticmethod
    def update_disciplina(disciplina_id, data):
        disciplina = db.session.get(Disciplina, disciplina_id)
        if not disciplina:
            return False, 'Disciplina não encontrada.'

        try:
            disciplina.materia = data.get('materia', disciplina.materia)
            disciplina.carga_horaria_prevista = int(data.get('carga_horaria_prevista', disciplina.carga_horaria_prevista))
            
            if 'carga_horaria_cumprida' in data:
                disciplina.carga_horaria_cumprida = int(data.get('carga_horaria_cumprida') or 0)
                
            disciplina.ciclo_id = int(data.get('ciclo_id', disciplina.ciclo_id))
            db.session.commit()
            return True, 'Disciplina atualizada com sucesso!'
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro update disciplina: {e}")
            return False, f'Erro: {str(e)}'

    @staticmethod
    def delete_disciplina(disciplina_id):
        disciplina = db.session.get(Disciplina, disciplina_id)
        if not disciplina:
            return False, 'Disciplina não encontrada.'

        try:
            db.session.delete(disciplina)
            db.session.commit()
            return True, 'Disciplina excluída com sucesso!'
        except Exception as e:
            db.session.rollback()
            return False, 'Erro ao excluir (verifique vínculos).'

    # --- NOVO CÁLCULO DE PROGRESSO (REFEITO TOTALMENTE) ---

    @staticmethod
    def get_dados_progresso(disciplina, pelotao_nome=None):
        """
        Calcula o progresso baseado ESTRITAMENTE no Quadro de Horários.
        Ignora duplicidade de instrutores.
        Conta:
        - Realizado: Aulas no quadro com data <= hoje.
        - Agendado: Aulas no quadro com data > hoje.
        """
        
        # 1. Busca todos os horários confirmados desta disciplina vinculados a semanas
        query = (
            select(Horario, Semana)
            .join(Semana)
            .where(
                Horario.disciplina_id == disciplina.id,
                Horario.status == 'confirmado'
            )
        )
        
        # Filtro opcional por pelotão, caso a arquitetura exija (geralmente não usado na visão geral)
        if pelotao_nome:
            query = query.where(Horario.pelotao == pelotao_nome)

        rows = db.session.execute(query).all()

        today = date.today()
        
        # Conjuntos para garantir unicidade do slot (Data + Periodo)
        # Se houver 2 instrutores no mesmo dia/periodo, o slot é o mesmo, então conta 1x.
        slots_realizados = set()
        slots_agendados = set()
        
        carga_realizada = 0
        carga_agendada = 0

        # Helper para converter string de dia da semana em offset
        def get_dia_offset(dia_str):
            s = dia_str.lower().strip()
            if 'segunda' in s: return 0
            if 'terca' in s or 'terça' in s: return 1
            if 'quarta' in s: return 2
            if 'quinta' in s: return 3
            if 'sexta' in s: return 4
            if 'sabado' in s or 'sábado' in s: return 5
            if 'domingo' in s: return 6
            return 0

        for row in rows:
            horario = row[0]
            semana = row[1]
            
            offset = get_dia_offset(horario.dia_semana)
            data_aula = semana.data_inicio + timedelta(days=offset)
            
            # CHAVE ÚNICA: Data real da aula + Período da aula.
            # Isso mata o problema de instrutores duplos.
            chave_slot = (data_aula, horario.periodo)
            
            duracao = horario.duracao or 1
            
            if data_aula <= today:
                # É aula passada ou de hoje (Realizada)
                if chave_slot not in slots_realizados:
                    carga_realizada += duracao
                    slots_realizados.add(chave_slot)
            else:
                # É aula futura (Agendada)
                if chave_slot not in slots_agendados:
                    carga_agendada += duracao
                    slots_agendados.add(chave_slot)

        total_previsto = disciplina.carga_horaria_prevista or 1 # Evita divisão por zero
        
        # Porcentagens para a barra visual
        pct_realizado = (carga_realizada / total_previsto) * 100
        pct_agendado = (carga_agendada / total_previsto) * 100
        
        # Trava em 100% visualmente se passar
        if (pct_realizado + pct_agendado) > 100:
            # Se estourou, ajusta proporcionalmente ou apenas trunca o agendado visual
            if pct_realizado > 100:
                pct_realizado = 100
                pct_agendado = 0
            else:
                pct_agendado = 100 - pct_realizado

        return {
            'realizado': int(carga_realizada),
            'agendado': int(carga_agendada),
            'previsto': int(total_previsto),
            'restante_para_planejar': int(total_previsto - (carga_realizada + carga_agendada)),
            'pct_realizado': round(pct_realizado, 1),
            'pct_agendado': round(pct_agendado, 1)
        }

    @staticmethod
    def sincronizar_progresso_aulas(school_id=None):
        """
        Mantive o método para compatibilidade com rotas existentes, 
        mas a lógica de visualização agora é "Live" via get_dados_progresso.
        Este método pode ser usado para atualizar o campo cacheado se necessário futuramente.
        """
        return True, "Sincronização não é mais necessária com a nova lógica de tempo real."