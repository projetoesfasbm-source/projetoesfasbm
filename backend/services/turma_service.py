# backend/services/turma_service.py

from flask import current_app
from sqlalchemy import select
from datetime import datetime
from ..models.database import db
from ..models.turma import Turma
from ..models.aluno import Aluno
from ..models.disciplina_turma import DisciplinaTurma
from ..models.turma_cargo import TurmaCargo
from ..models.historico import HistoricoAluno # Importa o modelo de histórico

class TurmaService:
    @staticmethod
    def create_turma(data, school_id):
        """Cria uma nova turma para uma escola específica."""
        nome_turma = data.get('nome')
        ano = data.get('ano')
        alunos_ids = data.get('alunos_ids', [])

        if not all([nome_turma, ano, school_id]):
            return False, 'Nome, Ano e ID da Escola são obrigatórios.'

        if db.session.execute(select(Turma).filter_by(nome=nome_turma, school_id=school_id)).scalar_one_or_none():
            return False, f'Uma turma com o nome "{nome_turma}" já existe nesta escola.'

        try:
            nova_turma = Turma(nome=nome_turma, ano=int(ano), school_id=school_id)
            db.session.add(nova_turma)
            db.session.flush()

            if alunos_ids:
                db.session.query(Aluno).filter(Aluno.id.in_(alunos_ids)).update({"turma_id": nova_turma.id})
            
            db.session.commit()
            return True, "Turma cadastrada com sucesso!"
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao criar turma: {e}")
            return False, f"Erro ao criar turma: {str(e)}"

    @staticmethod
    def update_turma(turma_id, data):
        """Atualiza os dados de uma turma e a lista de seus alunos."""
        turma = db.session.get(Turma, turma_id)
        if not turma:
            return False, "Turma não encontrada."
            
        novo_nome = data.get('nome')
        if db.session.execute(select(Turma).where(Turma.nome == novo_nome, Turma.id != turma_id, Turma.school_id == turma.school_id)).scalar_one_or_none():
            return False, f'Já existe outra turma com o nome "{novo_nome}" nesta escola.'
            
        try:
            turma.nome = novo_nome
            turma.ano = data.get('ano')
            
            alunos_ids_selecionados = data.get('alunos_ids', [])
            
            db.session.query(Aluno).filter(Aluno.turma_id == turma_id).update({"turma_id": None})
            
            if alunos_ids_selecionados:
                db.session.query(Aluno).filter(Aluno.id.in_(alunos_ids_selecionados)).update({"turma_id": turma_id})
                
            db.session.commit()
            return True, "Turma atualizada com sucesso!"
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao atualizar turma: {e}")
            return False, f"Erro ao atualizar turma: {str(e)}"

    @staticmethod
    def delete_turma(turma_id):
        """Exclui uma turma e todos os seus vínculos associados."""
        turma = db.session.get(Turma, turma_id)
        if not turma:
            return False, 'Turma não encontrada.'

        try:
            nome_turma_excluida = turma.nome
            
            db.session.query(Aluno).filter(Aluno.turma_id == turma_id).update({"turma_id": None})
            
            db.session.query(TurmaCargo).filter_by(turma_id=turma_id).delete()
            db.session.query(DisciplinaTurma).filter_by(pelotao=turma.nome).delete()
            
            db.session.delete(turma)
            db.session.commit()
            return True, f'Turma "{nome_turma_excluida}" e todos os seus vínculos foram excluídos com sucesso!'
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao excluir turma: {e}")
            return False, f'Erro ao excluir a turma: {str(e)}'

    # --- FUNÇÃO ADICIONADA ---
    # Esta função busca turmas filtrando pelo school_id, corrigindo o vazamento
    # de dados em telas como a de cadastro de aluno.
    @staticmethod
    def get_turmas_by_school(school_id):
        """
        Busca todas as turmas pertencentes a uma escola específica.
        Esta é a função correta para preencher dropdowns e listagens.
        """
        if not school_id:
            current_app.logger.warn("Tentativa de buscar turmas sem um school_id.")
            return []
            
        try:
            return db.session.scalars(
                select(Turma)
                .where(Turma.school_id == school_id)
                .order_by(Turma.nome)
            ).all()
        except Exception as e:
            current_app.logger.error(f"Erro ao buscar turmas por escola: {e}")
            return []
    # --- FIM DA FUNÇÃO ADICIONADA ---

    @staticmethod
    def get_cargos_da_turma(turma_id, cargos_lista):
        """Busca os cargos de uma turma e garante que todos da lista existam."""
        cargos_db = db.session.scalars(
            select(TurmaCargo).where(TurmaCargo.turma_id == turma_id)
        ).all()
        cargos_atuais = {cargo.cargo_nome: cargo.aluno_id for cargo in cargos_db}

        for cargo in cargos_lista:
            cargos_atuais.setdefault(cargo, None)
        return cargos_atuais

    @staticmethod
    def atualizar_cargos(turma_id, form_data):
        """Cria ou atualiza os cargos de uma turma, registrando no histórico."""
        turma = db.session.get(Turma, turma_id)
        if not turma:
            return False, 'Turma não encontrada.'
        
        try:
            cargo_nome = form_data.get('cargo_nome')
            aluno_id = int(form_data.get('aluno_id')) if form_data.get('aluno_id') else None
            data_evento_str = form_data.get('data_evento')
            data_evento = datetime.strptime(data_evento_str, '%Y-%m-%d') if data_evento_str else datetime.utcnow()

            cargo_atual = db.session.scalars(
                select(TurmaCargo).where(TurmaCargo.turma_id == turma_id, TurmaCargo.cargo_nome == cargo_nome)
            ).first()

            # Se um aluno está sendo removido do cargo
            if cargo_atual and cargo_atual.aluno_id and not aluno_id:
                historico_antigo = db.session.scalars(select(HistoricoAluno).where(
                    HistoricoAluno.aluno_id == cargo_atual.aluno_id,
                    HistoricoAluno.descricao.like(f"%Assumiu a função de {cargo_nome}%"),
                    HistoricoAluno.data_fim.is_(None)
                ).order_by(HistoricoAluno.data_inicio.desc())).first()
                if historico_antigo:
                    historico_antigo.data_fim = data_evento
                
                cargo_atual.aluno_id = None

            # Se um aluno está sendo ASSUMIDO ou TROCADO de cargo
            elif aluno_id:
                # Remove o aluno anterior, se houver
                if cargo_atual and cargo_atual.aluno_id:
                    historico_antigo = db.session.scalars(select(HistoricoAluno).where(
                        HistoricoAluno.aluno_id == cargo_atual.aluno_id,
                        HistoricoAluno.descricao.like(f"%Assumiu a função de {cargo_nome}%"),
                        HistoricoAluno.data_fim.is_(None)
                    ).order_by(HistoricoAluno.data_inicio.desc())).first()
                    if historico_antigo:
                        historico_antigo.data_fim = data_evento

                # Cria ou atualiza o cargo
                if cargo_atual:
                    cargo_atual.aluno_id = aluno_id
                else:
                    novo_cargo = TurmaCargo(turma_id=turma_id, cargo_nome=cargo_nome, aluno_id=aluno_id)
                    db.session.add(novo_cargo)

                # Cria novo registro no histórico para o novo aluno
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