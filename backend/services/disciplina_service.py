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

    # --- NOVO CÁLCULO DE PROGRESSO (SIMPLIFICADO E CORRETO) ---

    @staticmethod
    def get_dados_progresso(disciplina, pelotao_nome=None):
        """
        Calcula o progresso para exibição na barra.
        LÓGICA DEFINITIVA:
        1. Prioriza o valor 'carga_horaria_cumprida' do banco. Esse valor é alimentado
           pela função 'Sincronizar' (que lê os diários reais). Se tiver 34h lá, mostra 34h.
        2. Apenas se o banco estiver zerado, tenta estimar pelo quadro de horários (passado).
        """
        
        # Valor oficial (Sincronizado/Diários)
        horas_reais_banco = float(disciplina.carga_horaria_cumprida or 0)
        
        # Se temos horas registradas via diário/sync, usamos elas. É a verdade absoluta.
        if horas_reais_banco > 0:
            total_concluido = horas_reais_banco
        else:
            # FALLBACK: Se não tem diário lançado, estimamos pela grade para a barra não ficar vazia
            today = date.today()
            dias_passados = ['segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado', 'domingo'][:today.weekday() + 1]
            
            query = (
                select(Horario, Semana)
                .join(Semana)
                .where(
                    Horario.disciplina_id == disciplina.id,
                    Horario.status == 'confirmado',
                    or_(
                        Semana.data_fim < today,
                        and_(
                            Semana.data_inicio <= today,
                            Semana.data_fim >= today,
                            Horario.dia_semana.in_(dias_passados)
                        )
                    )
                )
            )
            
            if pelotao_nome:
                query = query.where(Horario.pelotao == pelotao_nome)

            rows = db.session.execute(query).all()
            
            # Deduplicação (mesma lógica de slots para evitar instrutor duplo contando 2x)
            slots_computados = set()
            estimativa_grade = 0
            
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
                chave = (data_aula, horario.periodo, horario.pelotao)
                
                if chave not in slots_computados:
                    estimativa_grade += (horario.duracao or 1)
                    slots_computados.add(chave)
            
            total_concluido = estimativa_grade

        # Cálculo da porcentagem
        carga_horaria_total = float(disciplina.carga_horaria_prevista or 0)
        percentual = 0
        if carga_horaria_total > 0:
            percentual = (total_concluido / carga_horaria_total) * 100
            
        return {
            'agendado': int(total_concluido),
            'previsto': int(carga_horaria_total),
            'percentual': min(round(percentual), 100)
        }

    @staticmethod
    def sincronizar_progresso_aulas(school_id=None):
        """
        Varre os Diários de Classe e atualiza o campo 'carga_horaria_cumprida'.
        Esta é a Fonte da Verdade.
        """
        try:
            query = select(Disciplina)
            if school_id:
                query = query.join(Turma, Disciplina.turma_id == Turma.id).where(Turma.school_id == school_id)
            
            disciplinas = db.session.scalars(query).all()
            updates_count = 0
            dias_map = {0: 'segunda', 1: 'terca', 2: 'quarta', 3: 'quinta', 4: 'sexta', 5: 'sabado', 6: 'domingo'}

            for disciplina in disciplinas:
                # Busca diários
                diarios = db.session.scalars(
                    select(DiarioClasse).where(DiarioClasse.disciplina_id == disciplina.id)
                ).all()
                
                # Datas únicas que tiveram aula registrada no diário
                datas_com_aula = set(d.data_aula for d in diarios)
                nova_carga = 0
                
                for data_aula in datas_com_aula:
                    # Para cada dia com diário, verificamos quantas horas-aula foram
                    # Buscamos na grade para saber a duração correta desse dia
                    dia_semana_str = dias_map.get(data_aula.weekday())
                    
                    horarios_do_dia = db.session.scalars(
                        select(Horario)
                        .join(Semana)
                        .where(
                            Horario.disciplina_id == disciplina.id,
                            Horario.dia_semana == dia_semana_str,
                            Semana.data_inicio <= data_aula,
                            Semana.data_fim >= data_aula
                        )
                    ).all()
                    
                    # Soma duração dos períodos únicos (evita duplicar se houver co-docência)
                    periodos_contabilizados = set()
                    horas_do_dia = 0
                    
                    for h in horarios_do_dia:
                        if h.periodo not in periodos_contabilizados:
                            duracao = h.duracao or 1
                            horas_do_dia += duracao
                            periodos_contabilizados.add(h.periodo)
                    
                    # Se não achou na grade (ex: aula extra), assume padrão de 2 tempos
                    if horas_do_dia == 0:
                         horas_do_dia = 2

                    nova_carga += horas_do_dia

                if disciplina.carga_horaria_cumprida != nova_carga:
                    disciplina.carga_horaria_cumprida = nova_carga
                    db.session.add(disciplina)
                    updates_count += 1
            
            db.session.commit()
            return True, f"{updates_count} disciplinas atualizadas com sucesso."
        except Exception as e:
            db.session.rollback()
            return False, f"Erro na sincronização: {str(e)}"