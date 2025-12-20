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
    
    # --- MÉTODOS DE CONSULTA (RESTAURADOS) ---
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
        Busca todas as disciplinas pertencentes a uma escola específica,
        juntando com as turmas para filtrar pelo school_id.
        """
        if not school_id:
            current_app.logger.warn("Tentativa de buscar disciplinas sem um school_id.")
            return []
            
        try:
            return db.session.scalars(
                select(Disciplina)
                .join(Disciplina.turma)
                .where(Turma.school_id == school_id)
                .order_by(Turma.nome, Disciplina.materia)
            ).all()
        except Exception as e:
            current_app.logger.error(f"Erro ao buscar disciplinas por escola: {e}")
            return []
    
    @staticmethod
    def get_by_id(id: int):
        """Busca disciplina por ID (método auxiliar para compatibilidade)."""
        return db.session.get(Disciplina, id)

    # --- MÉTODOS DE ESCRITA (CRUD RESTAURADOS) ---
    @staticmethod
    def create_disciplina(data, school_id):
        materia = data.get('materia')
        carga_horaria = data.get('carga_horaria_prevista')
        ciclo_id = data.get('ciclo_id')
        carga_cumprida = data.get('carga_horaria_cumprida', 0)
        turma_ids = data.get('turma_ids', []) # Recebe uma lista de IDs

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

                # Verifica se a disciplina já existe para esta turma específica
                if db.session.execute(select(Disciplina).where(Disciplina.materia == materia, Disciplina.turma_id == turma_id)).scalar_one_or_none():
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

                # Associa a disciplina aos alunos da turma selecionada
                for aluno in turma.alunos:
                    matricula = HistoricoDisciplina(aluno_id=aluno.id, disciplina_id=nova_disciplina.id)
                    db.session.add(matricula)
                
                success_count += 1
            except Exception as e:
                db.session.rollback() # Desfaz a transação atual para esta turma
                errors.append(f'Erro ao criar disciplina para a turma ID {turma_id}: {str(e)}')
                # Recomeça a sessão para a próxima iteração
                db.session.begin()

        if success_count > 0:
            db.session.commit()
        
        # Constrói a mensagem final
        message = f'{success_count} disciplina(s) criada(s) com sucesso. '
        if errors:
            message += f"Ocorreram {len(errors)} erro(s): " + "; ".join(errors)
        
        return success_count > 0, message

    @staticmethod
    def update_disciplina(disciplina_id, data):
        disciplina = db.session.get(Disciplina, disciplina_id)
        if not disciplina:
            return False, 'Disciplina não encontrada.'

        try:
            disciplina.materia = data.get('materia', disciplina.materia)
            disciplina.carga_horaria_prevista = int(data.get('carga_horaria_prevista', disciplina.carga_horaria_prevista))
            disciplina.carga_horaria_cumprida = int(data.get('carga_horaria_cumprida', disciplina.carga_horaria_cumprida) or 0)
            disciplina.ciclo_id = int(data.get('ciclo_id', disciplina.ciclo_id))
            # O turma_id não deve ser alterado na edição para manter a integridade.
            db.session.commit()
            return True, 'Disciplina atualizada com sucesso!'
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao atualizar disciplina: {e}")
            return False, 'Ocorreu um erro interno ao atualizar a disciplina.'

    @staticmethod
    def delete_disciplina(disciplina_id):
        disciplina = db.session.get(Disciplina, disciplina_id)
        if not disciplina:
            return False, 'Disciplina não encontrada.'

        try:
            db.session.delete(disciplina)
            db.session.commit()
            return True, 'Disciplina e todos os seus registros associados foram excluídos com sucesso!'
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao excluir disciplina: {e}")
            return False, 'Ocorreu um erro interno ao excluir a disciplina.'

    # --- MÉTODOS DE PROGRESSO E SINCRONIZAÇÃO (CORRIGIDOS) ---

    @staticmethod
    def get_dados_progresso(disciplina, pelotao_nome=None):
        """
        Calcula o progresso da disciplina com lógica de DEDUPLICAÇÃO.
        Isso impede que aulas com dois instrutores contem como carga horária dobrada.
        """
        today = date.today()
        
        # Mapeamento para filtro de dias passados na semana atual
        today_weekday_index = today.weekday()
        dias_da_semana = ['segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado', 'domingo']
        dias_passados_na_semana = dias_da_semana[:today_weekday_index + 1] # Inclui hoje

        # 1. Busca os horários candidatos (aulas passadas ou de hoje)
        # Trazemos o objeto Horario completo e a Semana para calcular unicidade
        query = (
            select(Horario, Semana)
            .join(Semana)
            .where(
                Horario.disciplina_id == disciplina.id,
                Horario.status == 'confirmado', # Filtra apenas confirmados
                or_(
                    Semana.data_fim < today,
                    and_(
                        Semana.data_inicio <= today,
                        Semana.data_fim >= today,
                        Horario.dia_semana.in_(dias_passados_na_semana)
                    )
                )
            )
        )

        if pelotao_nome:
            query = query.where(Horario.pelotao == pelotao_nome)

        rows = db.session.execute(query).all()
        
        # 2. Lógica de Agregação Segura (Deduplicação)
        # Usamos um conjunto (set) para armazenar 'slots' de tempo únicos.
        # Se houver 2 instrutores na mesma sala (mesma data, mesmo período),
        # teremos 2 linhas no banco, mas a chave do slot será a mesma, contando apenas 1x.
        
        slots_computados = set()
        aulas_concluidas_reais = 0
        
        # Função auxiliar para offset do dia
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
            
            # Calcula data real da aula
            offset = get_dia_offset(horario.dia_semana)
            data_aula = semana.data_inicio + timedelta(days=offset)
            
            # Chave única: (Data Real, Periodo, Pelotao)
            # Isso garante que se houver 2 registros para o mesmo horário (co-docência), só conta 1 vez.
            chave_slot = (data_aula, horario.periodo, horario.pelotao)
            
            if chave_slot not in slots_computados:
                duracao = horario.duracao or 1
                aulas_concluidas_reais += duracao
                slots_computados.add(chave_slot)

        # 3. Calcula totais
        # Soma o calculado real + o ajuste manual (se houver)
        total_concluido = aulas_concluidas_reais + disciplina.carga_horaria_cumprida
        carga_horaria_total = disciplina.carga_horaria_prevista
        
        percentual = 0
        if carga_horaria_total > 0:
            percentual = (total_concluido / carga_horaria_total) * 100
            
        return {
            'agendado': int(total_concluido),
            'previsto': carga_horaria_total,
            'percentual': min(round(percentual), 100)
        }

    @staticmethod
    def sincronizar_progresso_aulas(school_id=None):
        """
        Recalcula a 'carga_horaria_cumprida' de todas as disciplinas
        baseado nos Diários de Classe lançados e na duração cadastrada no Horário.
        """
        try:
            # 1. Busca todas as disciplinas (opcionalmente filtra por escola)
            query = select(Disciplina)
            if school_id:
                # Assumindo que Disciplina -> Turma -> School
                from ..models.turma import Turma
                query = query.join(Turma).where(Turma.school_id == school_id)
            
            disciplinas = db.session.scalars(query).all()
            
            updates_count = 0
            
            dias_map = {0: 'segunda', 1: 'terca', 2: 'quarta', 3: 'quinta', 4: 'sexta', 5: 'sabado', 6: 'domingo'}

            for disciplina in disciplinas:
                # 2. Busca todos os diários lançados para esta disciplina
                diarios = db.session.scalars(
                    select(DiarioClasse)
                    .where(DiarioClasse.disciplina_id == disciplina.id)
                ).all()
                
                # Agrupa datas unicas para evitar duplicidade se houver multiplos registros no mesmo dia
                datas_com_aula = set(d.data_aula for d in diarios)
                
                nova_carga_calculada = 0
                
                for data_aula in datas_com_aula:
                    dia_semana_str = dias_map.get(data_aula.weekday())
                    
                    # 3. Busca a duração prevista no Horário para aquele dia específico
                    # Trazemos Horario + Semana para validar vigência
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
                    
                    # DEDUPLICAÇÃO DE HORÁRIOS NO MESMO DIA (para evitar soma dobrada se houver 2 instrutores)
                    # Usamos um set de periodos para contar cada tempo de aula apenas uma vez
                    periodos_contabilizados = set()
                    horas_do_dia = 0
                    
                    for h in horarios_do_dia:
                        if h.periodo not in periodos_contabilizados:
                            duracao = h.duracao or 1
                            horas_do_dia += duracao
                            periodos_contabilizados.add(h.periodo)
                    
                    # Se não houver horário cadastrado na grade (aula extra ou erro),
                    # assumimos 2 tempos por padrão.
                    if horas_do_dia == 0 and horarios_do_dia:
                         # Fallback se a lista não for vazia mas soma for 0 (raro)
                         horas_do_dia = 2
                    elif not horarios_do_dia:
                         # Se não achou horário na grade para o dia do diário
                         horas_do_dia = 2

                    nova_carga_calculada += horas_do_dia

                # 4. Atualiza no banco se mudou
                if disciplina.carga_horaria_cumprida != nova_carga_calculada:
                    disciplina.carga_horaria_cumprida = nova_carga_calculada
                    db.session.add(disciplina)
                    updates_count += 1
            
            db.session.commit()
            return True, f"{updates_count} disciplinas tiveram seu progresso recalculado."
            
        except Exception as e:
            db.session.rollback()
            return False, str(e)