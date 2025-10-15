# backend/services/aluno_service.py

import os
import uuid
from datetime import datetime
from flask import current_app, session
from werkzeug.utils import secure_filename
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from ..models.database import db
from ..models.aluno import Aluno
from ..models.user import User
from ..models.historico import HistoricoAluno
from ..models.turma import Turma
from ..models.disciplina import Disciplina
from ..models.historico_disciplina import HistoricoDisciplina
from ..models.user_school import UserSchool
from utils.image_utils import allowed_file
from utils.normalizer import normalize_name

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def _save_profile_picture(file):
    """Valida e salva a imagem de perfil; retorna o nome do arquivo salvo ou uma mensagem de erro."""
    if not file:
        return None, "Nenhum arquivo enviado."
    
    # Garante que o stream está no início antes de validar
    file.stream.seek(0)
    if not allowed_file(file.filename, file.stream, ALLOWED_EXTENSIONS):
        return None, "Tipo de arquivo de imagem não permitido."
    
    try:
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4()}.{ext}"
        upload_folder = os.path.join(current_app.static_folder, 'uploads', 'profile_pics')
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, unique_filename)
        
        # Garante que o stream está no início antes de salvar
        file.stream.seek(0)
        file.save(file_path)
        
        return unique_filename, "Arquivo salvo com sucesso"
    except Exception as e:
        current_app.logger.error(f"Erro ao salvar foto de perfil: {e}")
        return None, "Erro ao salvar o arquivo de imagem."


class AlunoService:
    @staticmethod
    def get_all_alunos(user, nome_turma=None, search_term=None, page=1, per_page=15):
        stmt = (
            select(Aluno)
            .join(User, Aluno.user_id == User.id)
            .join(UserSchool, UserSchool.user_id == User.id)
            .where(
                User.is_active.is_(True),
                User.role == 'aluno',
            )
            .options(
                joinedload(Aluno.user),
                joinedload(Aluno.turma),
            )
            .order_by(User.nome_completo, User.matricula)
        )

        school_filter_ids = None
        if user.role in ['super_admin', 'programador']:
            view_as = session.get('view_as_school_id')
            if view_as:
                school_filter_ids = [int(view_as)]
        else:
            school_filter_ids = [us.school_id for us in getattr(user, 'user_schools', [])] or []

        if school_filter_ids is not None:
            if not school_filter_ids:
                return db.paginate(select(Aluno).where(db.false()), page=page, per_page=per_page)
            stmt = stmt.where(UserSchool.school_id.in_(school_filter_ids))

        if nome_turma:
            stmt = stmt.join(Turma, Aluno.turma_id == Turma.id).where(Turma.nome == nome_turma)
        
        if search_term:
            like_term = f"%{search_term}%"
            stmt = stmt.where(
                or_(
                    User.nome_completo.ilike(like_term),
                    User.matricula.ilike(like_term)
                )
            )

        alunos_paginados = db.paginate(stmt, page=page, per_page=per_page, error_out=False)
        return alunos_paginados

    @staticmethod
    def get_aluno_by_id(aluno_id: int):
        return db.session.get(Aluno, aluno_id)
        
    @staticmethod
    def update_profile_picture(aluno_id: int, file):
        aluno = db.session.get(Aluno, aluno_id)
        if not aluno:
            return False, "Aluno não encontrado."

        if file:
            # Remove a foto antiga se não for a padrão
            if aluno.foto_perfil and aluno.foto_perfil != 'default.png':
                old_path = os.path.join(current_app.static_folder, 'uploads', 'profile_pics', aluno.foto_perfil)
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except Exception as e:
                        current_app.logger.error(f"Não foi possível remover a foto antiga: {e}")

            # Salva a nova foto
            filename, msg = _save_profile_picture(file)
            if filename:
                aluno.foto_perfil = filename
                return True, "Foto de perfil atualizada com sucesso."
            else:
                return False, msg
        return False, "Nenhum arquivo de imagem fornecido."

    @staticmethod
    def update_aluno(aluno_id: int, data: dict):
        aluno = db.session.get(Aluno, aluno_id)
        if not aluno:
            return False, "Aluno não encontrado."

        nome_completo = normalize_name(data.get('nome_completo'))
        email_novo = (data.get('email') or '').strip()
        opm = (data.get('opm') or '').strip()
        turma_id_val = data.get('turma_id')

        if not all([nome_completo, opm, email_novo, turma_id_val]):
            return False, "Todos os campos de dados básicos são obrigatórios."

        try:
            if aluno.user and aluno.user.email != email_novo:
                if db.session.scalar(select(User).where(User.email == email_novo, User.id != aluno.user.id)):
                    return False, "O e-mail fornecido já está em uso por outra conta."

            if aluno.user:
                aluno.user.nome_completo = nome_completo
                aluno.user.email = email_novo
                posto_selecionado = data.get('posto_graduacao')
                if posto_selecionado == 'Outro':
                    aluno.user.posto_graduacao = data.get('posto_graduacao_outro')
                else:
                    aluno.user.posto_graduacao = posto_selecionado

            aluno.opm = opm
            aluno.turma_id = int(turma_id_val)

            db.session.commit()
            return True, "Perfil do aluno atualizado com sucesso!"

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro inesperado ao atualizar aluno: {e}")
            return False, f"Ocorreu um erro inesperado ao atualizar o perfil. Detalhes: {str(e)}"
            
    @staticmethod
    def update_funcao_aluno(aluno_id: int, form_data: dict):
        aluno = db.session.get(Aluno, aluno_id)
        if not aluno:
            return False, "Aluno não encontrado."
        
        try:
            funcao_nova = form_data.get('funcao_atual')
            data_evento_str = form_data.get('data_evento')
            data_evento = datetime.strptime(data_evento_str, '%Y-%m-%d') if data_evento_str else datetime.utcnow()
            
            funcao_antiga = aluno.funcao_atual

            if funcao_antiga and funcao_antiga != funcao_nova:
                historico_antigo = db.session.scalars(select(HistoricoAluno).where(
                    HistoricoAluno.aluno_id == aluno_id,
                    HistoricoAluno.tipo == 'Função de Escola',
                    HistoricoAluno.descricao.like(f"%Assumiu a função de {funcao_antiga}%"),
                    HistoricoAluno.data_fim.is_(None)
                ).order_by(HistoricoAluno.data_inicio.desc())).first()
                if historico_antigo:
                    historico_antigo.data_fim = data_evento

            if funcao_nova and funcao_nova != funcao_antiga:
                novo_historico = HistoricoAluno(
                    aluno_id=aluno_id,
                    tipo='Função de Escola',
                    descricao=f'Assumiu a função de {funcao_nova}.',
                    data_inicio=data_evento
                )
                db.session.add(novo_historico)

            aluno.funcao_atual = funcao_nova if funcao_nova else None
            
            db.session.commit()
            return True, "Função do aluno atualizada com sucesso!"
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao atualizar função do aluno: {e}")
            return False, "Ocorreu um erro ao atualizar a função."

    @staticmethod
    def delete_aluno(aluno_id: int):
        aluno = db.session.get(Aluno, aluno_id)
        if not aluno:
            return False, "Aluno não encontrado."

        try:
            user_a_deletar = aluno.user
            if user_a_deletar:
                db.session.delete(user_a_deletar)
                db.session.commit()
                return True, "Aluno e todos os seus registros foram excluídos com sucesso!"
            else:
                db.session.delete(aluno)
                db.session.commit()
                return True, "Perfil de aluno órfão removido com sucesso."
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao excluir aluno: {e}")
            return False, f"Erro ao excluir aluno: {str(e)}"