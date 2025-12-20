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
        return db.session.scalars(select(Disciplina).order_by(Disciplina.materia)).all()

    @staticmethod
    def get_disciplinas_by_turma(turma_id):
        return db.session.scalars(
            select(Disciplina)
            .where(Disciplina.turma_id == turma_id)
            .order_by(Disciplina.materia)
        ).all()

    @staticmethod
    def get_disciplinas_by_school(school_id):
        if not school_id: return []
        stmt = (
            select(Disciplina)
            .join(Turma, Disciplina.turma_id == Turma.id)
            .where(Turma.school_id == school_id)
            .order_by(Turma.nome, Disciplina.materia)
        )
        return db.session.scalars(stmt).all()

    @staticmethod
    def get_by_id(id: int):
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
                    errors.append(f'Turma {turma_id}: Inválida ou outra escola.')
                    continue

                exists = db.session.execute(
                    select(Disciplina).where(Disciplina.materia == materia, Disciplina.turma_id == turma_id)
                ).scalar_one_or_none()
                
                if exists:
                    errors.append(f'Disciplina "{materia}" já existe na turma {turma.nome}.')
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
                        db.session.add(HistoricoDisciplina(aluno_id=aluno.id, disciplina_id=nova_disciplina.id))
                
                success_count += 1
            except Exception as e:
                db.session.rollback()
                errors.append(f'Erro turma {turma_id}: {str(e)}')
                db.session.begin()

        if success_count > 0: db.session.commit()
        return success_count > 0, f'{success_count} criada(s). ' + ("; ".join(errors) if errors else "")

    @staticmethod
    def update_disciplina(disciplina_id, data):
        disciplina = db.session.get(Disciplina, disciplina_id)
        if not disciplina: return False, 'Não encontrada.'
        try:
            disciplina.materia = data.get('materia', disciplina.materia)
            disciplina.carga_horaria_prevista = int(data.get('carga_horaria_prevista', disciplina.carga_horaria_prevista))
            if 'carga_horaria_cumprida' in data:
                disciplina.carga_horaria_cumprida = int(data.get('carga_horaria_cumprida') or 0)
            disciplina.ciclo_id = int(data.get('ciclo_id', disciplina.ciclo_id))
            db.session.commit()
            return True, 'Atualizada com sucesso!'
        except Exception as e:
            db.session.rollback()
            return False, f'Erro: {str(e)}'

    @staticmethod
    def delete_disciplina(disciplina_id):
        disciplina = db.session.get(Disciplina, disciplina_id)
        if not disciplina: return False, 'Não encontrada.'
        try:
            db.session.delete(disciplina)
            db.session.commit()
            return True, 'Excluída com sucesso!'
        except Exception as e:
            db.session.rollback()
            return False, 'Erro ao excluir (verifique vínculos).'

    # --- CÁLCULO DE PROGRESSO (CORRIGIDO: USA DURACAO E NÃO PERIODOS) ---

    @staticmethod
    def get_dados_progresso(disciplina):
        """
        Calcula o progresso lendo TODAS as semanas e somando a DURACAO das aulas.
        """
        
        # Garante que o objeto turma está acessível para pegar o nome
        if not disciplina.turma:
             return {'realizado': 0, 'agendado': 0, 'previsto': 0, 'restante_para_planejar': 0, 'pct_realizado': 0, 'pct_agendado': 0}

        nome_pelotao = disciplina.turma.nome

        # 1. Busca TUDO da tabela Horario para esta disciplina
        # Filtramos por Horario.pelotao (string) == disciplina.turma.nome
        stmt = (
            select(Horario, Semana)
            .join(Semana, Horario.semana_id == Semana.id)
            .where(
                Horario.disciplina_id == disciplina.id,
                Horario.pelotao == nome_pelotao
            )
        )
        
        results = db.session.execute(stmt).all()
        
        today = date.today()
        carga_realizada = 0
        carga_agendada = 0
        
        dia_map = {
            'segunda': 0, 'terca': 1, 'terça': 1, 'quarta': 2, 
            'quinta': 3, 'sexta': 4, 'sabado': 5, 'sábado': 5, 'domingo': 6
        }

        for row in results:
            horario = row[0]
            semana = row[1]
            
            # --- CORREÇÃO AQUI ---
            # O modelo Horario tem 'duracao' (int), não 'periodos' (string/list).
            # Se duracao for None, assumimos 1 tempo.
            qtd_aulas = horario.duracao if horario.duracao else 1
            
            if qtd_aulas > 0:
                # Calcula a data exata da aula para separar Passado (Realizado) vs Futuro (Agendado)
                nome_dia = (horario.dia_semana or '').lower()
                offset = 0
                for chave, val in dia_map.items():
                    if chave in nome_dia:
                        offset = val
                        break
                
                data_aula = semana.data_inicio + timedelta(days=offset)
                
                if data_aula <= today:
                    carga_realizada += qtd_aulas
                else:
                    carga_agendada += qtd_aulas

        total_previsto = disciplina.carga_horaria_prevista or 0
        base_calc = total_previsto if total_previsto > 0 else 1

        pct_realizado = (carga_realizada / base_calc) * 100
        pct_agendado = (carga_agendada / base_calc) * 100
        
        # Ajuste visual para não ultrapassar 100% na barra
        soma = pct_realizado + pct_agendado
        if soma > 100:
            scale = 100 / soma
            pct_realizado *= scale
            pct_agendado *= scale

        return {
            'realizado': carga_realizada,
            'agendado': carga_agendada,
            'previsto': total_previsto,
            'restante_para_planejar': total_previsto - (carga_realizada + carga_agendada),
            'pct_realizado': round(pct_realizado, 1),
            'pct_agendado': round(pct_agendado, 1)
        }

    @staticmethod
    def sincronizar_progresso_aulas(school_id=None):
        return True, "Sincronização automática ativa."