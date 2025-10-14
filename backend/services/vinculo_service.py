# backend/services/vinculo_service.py
from flask import current_app
from sqlalchemy import select, or_
from sqlalchemy.orm import joinedload

from ..models.database import db
from ..models.disciplina_turma import DisciplinaTurma
from ..models.turma import Turma
from ..models.instrutor import Instrutor
from ..models.disciplina import Disciplina


class VinculoService:
    @staticmethod
    def get_all_vinculos(turma_filtrada_id: int = None):
        query = db.select(DisciplinaTurma).options(
            joinedload(DisciplinaTurma.instrutor_1).joinedload(Instrutor.user),
            joinedload(DisciplinaTurma.instrutor_2).joinedload(Instrutor.user),
            joinedload(DisciplinaTurma.disciplina).joinedload(Disciplina.ciclo),
            joinedload(DisciplinaTurma.disciplina).joinedload(Disciplina.turma) # Carrega a turma através da disciplina
        )

        if turma_filtrada_id:
            # Filtra juntando a tabela de disciplinas e depois a de turmas
            query = query.join(Disciplina).where(Disciplina.turma_id == turma_filtrada_id)

        query = query.order_by(DisciplinaTurma.id.desc())
        return db.session.scalars(query).all()

    @staticmethod
    def add_vinculo(data: dict):
        disciplina_id = data.get('disciplina_id')
        instrutor_id_1 = data.get('instrutor_id_1')
        instrutor_id_2 = data.get('instrutor_id_2')

        if not disciplina_id:
            return False, 'A disciplina é obrigatória.'
        
        if not instrutor_id_1 and not instrutor_id_2:
            return False, 'Pelo menos um instrutor deve ser selecionado.'

        instrutor_1 = int(instrutor_id_1) if instrutor_id_1 else 0
        instrutor_2 = int(instrutor_id_2) if instrutor_id_2 else 0

        if instrutor_1 > 0 and instrutor_1 == instrutor_2:
            return False, 'Os instrutores 1 e 2 não podem ser a mesma pessoa.'

        # --- LÓGICA CORRIGIDA ---
        disciplina = db.session.get(Disciplina, disciplina_id)
        if not disciplina or not disciplina.turma:
            return False, 'Disciplina ou turma associada não encontrada.'
        
        pelotao_nome = disciplina.turma.nome
        # --- FIM DA CORREÇÃO ---

        vinculo_existente = db.session.scalars(select(DisciplinaTurma).filter_by(
            disciplina_id=disciplina_id,
            pelotao=pelotao_nome # Adicionado para garantir a verificação correta
        )).first()

        try:
            if vinculo_existente:
                return False, 'Já existe um vínculo para esta disciplina nesta turma. Edite o vínculo existente na lista.'
            else:
                novo_vinculo = DisciplinaTurma(
                    pelotao=pelotao_nome, # --- CAMPO ADICIONADO ---
                    disciplina_id=disciplina_id,
                    instrutor_id_1=instrutor_1 if instrutor_1 > 0 else None,
                    instrutor_id_2=instrutor_2 if instrutor_2 > 0 else None
                )
                db.session.add(novo_vinculo)
                message = 'Vínculo criado com sucesso!'
            
            db.session.commit()
            return True, message
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao adicionar vínculo: {e}")
            return False, f"Erro ao adicionar vínculo: {str(e)}"

    @staticmethod
    def edit_vinculo(vinculo_id: int, data: dict):
        vinculo = db.session.get(DisciplinaTurma, vinculo_id)
        if not vinculo:
            return False, 'Vínculo não encontrado.'

        disciplina_id = data.get('disciplina_id')
        instrutor_id_1 = data.get('instrutor_id_1')
        instrutor_id_2 = data.get('instrutor_id_2')

        if not disciplina_id:
            return False, 'A disciplina é obrigatória.'
            
        if not instrutor_id_1 and not instrutor_id_2:
            return False, 'Pelo menos um instrutor deve ser selecionado.'
        
        instrutor_1 = int(instrutor_id_1) if instrutor_id_1 else 0
        instrutor_2 = int(instrutor_id_2) if instrutor_id_2 else 0

        if instrutor_1 > 0 and instrutor_1 == instrutor_2:
            return False, 'Os instrutores 1 e 2 não podem ser a mesma pessoa.'

        # --- LÓGICA CORRIGIDA ---
        disciplina = db.session.get(Disciplina, disciplina_id)
        if not disciplina or not disciplina.turma:
            return False, 'Disciplina ou turma associada não encontrada.'
        
        pelotao_nome = disciplina.turma.nome
        # --- FIM DA CORREÇÃO ---

        try:
            vinculo.pelotao = pelotao_nome # --- CAMPO ADICIONADO ---
            vinculo.disciplina_id = disciplina_id
            vinculo.instrutor_id_1 = instrutor_1 if instrutor_1 > 0 else None
            vinculo.instrutor_id_2 = instrutor_2 if instrutor_2 > 0 else None
            
            db.session.commit()
            return True, 'Vínculo atualizado com sucesso!'
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao editar vínculo: {e}")
            return False, f"Erro ao editar vínculo: {str(e)}"

    @staticmethod
    def delete_vinculo(vinculo_id: int):
        vinculo = db.session.get(DisciplinaTurma, vinculo_id)
        if not vinculo:
            return False, 'Vínculo não encontrado.'

        try:
            db.session.delete(vinculo)
            db.session.commit()
            return True, 'Vínculo excluído com sucesso!'
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao excluir vínculo: {e}")
            return False, f"Erro ao excluir vínculo: {str(e)}"