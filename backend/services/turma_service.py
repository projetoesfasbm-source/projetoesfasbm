# backend/services/turma_service.py

from flask import current_app
from sqlalchemy import select
from datetime import datetime
from ..models.database import db
from ..models.turma import Turma
from ..models.aluno import Aluno
from ..models.disciplina_turma import DisciplinaTurma
from ..models.turma_cargo import TurmaCargo
from ..models.historico import HistoricoAluno 
# --- IMPORTAÇÕES NECESSÁRIAS PARA A CORREÇÃO ---
from ..models.disciplina import Disciplina
from ..models.horario import Horario

class TurmaService:
    @staticmethod
    def create_turma(data, school_id):
        """Cria uma nova turma para uma escola específica."""
        nome_turma = data.get('nome')
        # CORREÇÃO: Não converte mais para int
        ano = data.get('ano')
        status = data.get('status')
        alunos_ids = data.get('alunos_ids', [])

        if not all([nome_turma, ano, school_id]):
            return False, 'Nome, Ano e ID da Escola são obrigatórios.'

        if db.session.execute(select(Turma).filter_by(nome=nome_turma, school_id=school_id)).scalar_one_or_none():
            return False, f'Uma turma com o nome "{nome_turma}" já existe nesta escola.'

        try:
            nova_turma = Turma(
                nome=nome_turma, 
                ano=ano,  # Passa como string
                school_id=school_id
            )
            
            if status:
                 nova_turma.status = status

            db.session.add(nova_turma)
            db.session.flush()

            if alunos_ids:
                db.session.query(Aluno).filter(Aluno.id.in_(alunos_ids)).update(
                    {"turma_id": nova_turma.id}, 
                    synchronize_session=False
                )
            
            db.session.commit()
            return True, "Turma cadastrada com sucesso!"
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao criar turma: {e}")
            return False, f"Erro ao criar turma: {str(e)}"

    @staticmethod
    def update_turma(turma_id, data):
        """Atualiza os dados de uma turma."""
        turma = db.session.get(Turma, turma_id)
        if not turma:
            return False, "Turma não encontrada."
            
        novo_nome = data.get('nome')
        
        # Verifica duplicidade (exceto a própria turma)
        if db.session.execute(select(Turma).where(
            Turma.nome == novo_nome, 
            Turma.id != turma_id, 
            Turma.school_id == turma.school_id
        )).scalar_one_or_none():
            return False, f'Já existe outra turma com o nome "{novo_nome}" nesta escola.'
            
        try:
            turma.nome = novo_nome
            # CORREÇÃO: Não converte mais para int
            turma.ano = data.get('ano')
            
            status = data.get('status')
            if status:
                turma.status = status
            
            alunos_ids_selecionados = data.get('alunos_ids', [])
            
            # Atualiza vínculos
            db.session.query(Aluno).filter(Aluno.turma_id == turma_id).update(
                {"turma_id": None}, 
                synchronize_session=False
            )
            
            if alunos_ids_selecionados:
                db.session.query(Aluno).filter(Aluno.id.in_(alunos_ids_selecionados)).update(
                    {"turma_id": turma_id}, 
                    synchronize_session=False
                )
                
            db.session.commit()
            return True, "Turma atualizada com sucesso!"
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao atualizar turma: {e}")
            return False, f"Erro ao atualizar turma: {str(e)}"

    @staticmethod
    def delete_turma(turma_id):
        turma = db.session.get(Turma, turma_id)
        if not turma:
            return False, 'Turma não encontrada.'

        try:
            nome_turma_excluida = turma.nome
            
            # --- CORREÇÃO INÍCIO: Remove dependências de Horário ---
            # O banco impede excluir a Turma se ela tem Disciplinas que têm Horários vinculados.
            # Precisamos limpar os horários dessas disciplinas primeiro.
            
            # 1. Busca IDs das disciplinas pertencentes a esta turma
            disciplinas_ids = db.session.scalars(
                select(Disciplina.id).where(Disciplina.turma_id == turma_id)
            ).all()

            # 2. Exclui horários vinculados a essas disciplinas
            if disciplinas_ids:
                db.session.query(Horario).filter(Horario.disciplina_id.in_(disciplinas_ids)).delete(synchronize_session=False)
            # --- CORREÇÃO FIM ---

            # Desvincula alunos
            db.session.query(Aluno).filter(Aluno.turma_id == turma_id).update(
                {"turma_id": None}, 
                synchronize_session=False
            )
            
            # Remove cargos e vínculos extras
            db.session.query(TurmaCargo).filter_by(turma_id=turma_id).delete()
            db.session.query(DisciplinaTurma).filter_by(pelotao=turma.nome).delete()
            
            # Exclui a turma (as disciplinas serão excluídas em cascata pelo banco ou SQLAlchemy)
            db.session.delete(turma)
            db.session.commit()
            return True, f'Turma "{nome_turma_excluida}" e todos os seus vínculos foram excluídos com sucesso!'
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao excluir turma: {e}")
            return False, f'Erro ao excluir a turma: {str(e)}'

    @staticmethod
    def get_turmas_by_school(school_id):
        if not school_id:
            return []
            
        # CORREÇÃO: Removemos o try/except genérico que engolia erros de Enum
        return db.session.scalars(
            select(Turma)
            .where(Turma.school_id == school_id)
            .order_by(Turma.nome)
        ).all()

    @staticmethod
    def get_cargos_da_turma(turma_id, cargos_lista):
        cargos_db = db.session.scalars(
            select(TurmaCargo).where(TurmaCargo.turma_id == turma_id)
        ).all()
        cargos_atuais = {cargo.cargo_nome: cargo.aluno_id for cargo in cargos_db}

        for cargo in cargos_lista:
            cargos_atuais.setdefault(cargo, None)
        return cargos_atuais

    @staticmethod
    def atualizar_cargos(turma_id, form_data):
        turma = db.session.get(Turma, turma_id)
        if not turma:
            return False, 'Turma não encontrada.'
        
        try:
            cargo_nome = form_data.get('cargo_nome')
            aluno_id_str = form_data.get('aluno_id')
            aluno_id = int(aluno_id_str) if aluno_id_str else None
            
            data_evento_str = form_data.get('data_evento')
            if data_evento_str:
                data_evento = datetime.strptime(data_evento_str, '%Y-%m-%d')
            else:
                data_evento = datetime.utcnow()

            cargo_atual = db.session.scalars(
                select(TurmaCargo).where(TurmaCargo.turma_id == turma_id, TurmaCargo.cargo_nome == cargo_nome)
            ).first()

            if cargo_atual and cargo_atual.aluno_id and not aluno_id:
                historico_antigo = db.session.scalars(select(HistoricoAluno).where(
                    HistoricoAluno.aluno_id == cargo_atual.aluno_id,
                    HistoricoAluno.descricao.like(f"%Assumiu a função de {cargo_nome}%"),
                    HistoricoAluno.data_fim.is_(None)
                ).order_by(HistoricoAluno.data_inicio.desc())).first()
                if historico_antigo:
                    historico_antigo.data_fim = data_evento
                
                cargo_atual.aluno_id = None

            elif aluno_id:
                if cargo_atual and cargo_atual.aluno_id:
                    historico_antigo = db.session.scalars(select(HistoricoAluno).where(
                        HistoricoAluno.aluno_id == cargo_atual.aluno_id,
                        HistoricoAluno.descricao.like(f"%Assumiu a função de {cargo_nome}%"),
                        HistoricoAluno.data_fim.is_(None)
                    ).order_by(HistoricoAluno.data_inicio.desc())).first()
                    if historico_antigo:
                        historico_antigo.data_fim = data_evento

                if cargo_atual:
                    cargo_atual.aluno_id = aluno_id
                else:
                    novo_cargo = TurmaCargo(turma_id=turma_id, cargo_nome=cargo_nome, aluno_id=aluno_id)
                    db.session.add(novo_cargo)

                novo_historico = HistoricoAluno(
                    aluno_id=aluno_id,
                    tipo='Função de Turma',
                    descricao=f'Assumiu a função de {cargo_nome} na turma {turma.nome}.',
                    data_inicio=data_evento
                )
                db.session.add(novo_historico)
            
            db.session.commit()
            return True, 'Cargos da turma atualizados com sucesso!'
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao salvar os cargos: {e}")
            return False, 'Erro interno ao salvar os cargos.'