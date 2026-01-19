from flask import current_app
from sqlalchemy import select
from datetime import datetime
from ..models.database import db
from ..models.turma import Turma
from ..models.aluno import Aluno
from ..models.disciplina_turma import DisciplinaTurma
from ..models.turma_cargo import TurmaCargo
from ..models.historico import HistoricoAluno 
from ..models.disciplina import Disciplina
from ..models.horario import Horario

class TurmaService:

    @staticmethod
    def create_turma(data, school_id):
        nome_turma = data.get('nome')
        ano = data.get('ano')
        status = data.get('status')
        alunos_ids = data.get('alunos_ids', [])

        if not all([nome_turma, ano, school_id]):
            return False, 'Nome, Ano e ID da Escola são obrigatórios.'

        # Verifica duplicidade
        if db.session.execute(select(Turma).filter_by(nome=nome_turma, school_id=school_id)).scalar_one_or_none():
            return False, f'Uma turma com o nome "{nome_turma}" já existe nesta escola.'

        try:
            nova_turma = Turma(nome=nome_turma, ano=ano, school_id=school_id)
            if status: nova_turma.status = status
            
            db.session.add(nova_turma)
            db.session.flush()
            
            if alunos_ids:
                db.session.query(Aluno).filter(Aluno.id.in_(alunos_ids)).update({"turma_id": nova_turma.id}, synchronize_session=False)
            
            db.session.commit()
            return True, "Turma cadastrada com sucesso!"
        except Exception as e:
            db.session.rollback()
            return False, f"Erro: {str(e)}"

    @staticmethod
    def update_turma(turma_id, data):
        turma = db.session.get(Turma, turma_id)
        if not turma: return False, "Turma não encontrada."
        
        # Captura o nome antigo para verificação
        old_name = turma.nome
        new_name = data.get('nome')

        try:
            # 1. Atualiza dados básicos
            turma.nome = new_name
            turma.ano = data.get('ano')
            turma.status = data.get('status')
            
            # Atualiza data de formatura se vier no form
            if data.get('data_formatura'):
                turma.data_formatura = data.get('data_formatura')

            # --- CORREÇÃO: Lógica de Atualização de Alunos ---
            # O problema anterior era que este bloco não existia.
            
            ids_selecionados = data.get('alunos_ids')
            
            # Nota: Em formulários HTML/WTForms, se nenhum checkbox for marcado, 
            # 'alunos_ids' pode vir como None ou lista vazia []. Tratamos ambos.
            if ids_selecionados is not None:
                # A. REMOVER: Quem está na turma, mas NÃO está na lista nova (Desmarcados)
                if not ids_selecionados:
                    # Se a lista nova é vazia, remove TODO MUNDO dessa turma
                    db.session.query(Aluno).filter(Aluno.turma_id == turma_id).update({"turma_id": None}, synchronize_session=False)
                else:
                    # Remove apenas quem não está na lista de selecionados
                    db.session.query(Aluno).filter(
                        Aluno.turma_id == turma_id,
                        Aluno.id.notin_(ids_selecionados)
                    ).update({"turma_id": None}, synchronize_session=False)

                    # B. ADICIONAR: Vincula quem está na lista nova
                    db.session.query(Aluno).filter(
                        Aluno.id.in_(ids_selecionados)
                    ).update({"turma_id": turma_id}, synchronize_session=False)
            # ------------------------------------------------

            db.session.commit()

            # --- PROTEÇÃO CONTRA AULAS FANTASMAS ---
            if old_name != new_name:
                disciplinas_ids = db.session.scalars(
                    select(Disciplina.id).where(Disciplina.turma_id == turma_id)
                ).all()
                
                if disciplinas_ids:
                    db.session.query(Horario).filter(
                        Horario.disciplina_id.in_(disciplinas_ids)
                    ).update({Horario.pelotao: new_name}, synchronize_session=False)
                    
                    db.session.commit()
            # ---------------------------------------

            return True, "Turma atualizada com sucesso."
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def delete_turma(turma_id):
        turma = db.session.get(Turma, turma_id)
        if not turma: return False, 'Turma não encontrada.'
        try:
            # Remove horários vinculados
            disciplinas_ids = db.session.scalars(select(Disciplina.id).where(Disciplina.turma_id == turma_id)).all()
            if disciplinas_ids:
                db.session.query(Horario).filter(Horario.disciplina_id.in_(disciplinas_ids)).delete(synchronize_session=False)
            
            # Desvincula alunos (não apaga o aluno, só tira da turma)
            db.session.query(Aluno).filter(Aluno.turma_id == turma_id).update({"turma_id": None}, synchronize_session=False)
            
            # Remove cargos e vinculos
            db.session.query(TurmaCargo).filter_by(turma_id=turma_id).delete()
            db.session.query(DisciplinaTurma).filter_by(pelotao=turma.nome).delete()
            
            db.session.delete(turma)
            db.session.commit()
            return True, 'Turma excluída.'
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def get_turmas_by_school(school_id):
        if not school_id: return []
        return db.session.scalars(select(Turma).where(Turma.school_id == school_id).order_by(Turma.nome)).all()

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
            data_evento = datetime.strptime(data_evento_str, '%Y-%m-%d') if data_evento_str else datetime.utcnow()

            if cargo_nome not in TurmaCargo.get_all_roles():
                return False, f'O cargo "{cargo_nome}" não é um cargo oficial do sistema.'

            cargo_atual = db.session.scalars(
                select(TurmaCargo).where(TurmaCargo.turma_id == turma_id, TurmaCargo.cargo_nome == cargo_nome)
            ).first()

            # Lógica de Histórico
            if cargo_atual and cargo_atual.aluno_id and (cargo_atual.aluno_id != aluno_id):
                historico_antigo = db.session.scalars(select(HistoricoAluno).where(
                    HistoricoAluno.aluno_id == cargo_atual.aluno_id,
                    HistoricoAluno.descricao.like(f"%Assumiu a função de {cargo_nome}%"),
                    HistoricoAluno.data_fim.is_(None)
                ).order_by(HistoricoAluno.data_inicio.desc())).first()
                
                if historico_antigo:
                    historico_antigo.data_fim = data_evento

            if aluno_id:
                if not cargo_atual:
                    cargo_atual = TurmaCargo(turma_id=turma_id, cargo_nome=cargo_nome)
                    db.session.add(cargo_atual)
                
                if cargo_atual.aluno_id != aluno_id:
                    novo_historico = HistoricoAluno(
                        aluno_id=aluno_id,
                        tipo='Função de Turma',
                        descricao=f'Assumiu a função de {cargo_nome} na turma {turma.nome}.',
                        data_inicio=data_evento
                    )
                    db.session.add(novo_historico)
                
                cargo_atual.aluno_id = aluno_id
            
            else:
                if cargo_atual:
                    cargo_atual.aluno_id = None 

            db.session.commit()
            return True, f'Cargo "{cargo_nome}" atualizado com sucesso!'
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao salvar os cargos: {e}")
            return False, f'Erro interno: {str(e)}'