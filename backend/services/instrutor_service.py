# backend/services/instrutor_service.py

import os
import uuid
from flask import current_app, session
from werkzeug.utils import secure_filename
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from backend.models.database import db
from backend.models.instrutor import Instrutor
from backend.models.user import User
from backend.models.user_school import UserSchool
from utils.image_utils import allowed_file
from utils.normalizer import normalize_matricula, normalize_name

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def _save_profile_picture(file):
    """Valida e salva a imagem de perfil; retorna o nome do arquivo salvo ou uma mensagem de erro."""
    if not file:
        return None, "Nenhum arquivo enviado."
    
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
        
        file.stream.seek(0)
        file.save(file_path)
        
        return unique_filename, "Arquivo salvo com sucesso"
    except Exception as e:
        current_app.logger.error(f"Erro ao salvar foto de perfil: {e}")
        return None, "Erro ao salvar o arquivo de imagem."


class InstrutorService:
    @staticmethod
    def get_all_instrutores(user=None, search_term=None, page=1, per_page=15):
        """
        Lista instrutores de forma paginada e com filtro de busca.
        """
        stmt = (
            select(Instrutor)
            .join(User, Instrutor.user_id == User.id)
            .join(UserSchool, UserSchool.user_id == User.id)
            .where(
                User.is_active.is_(True),
                User.role == 'instrutor',
            )
            .options(joinedload(Instrutor.user))
            .order_by(User.nome_completo, User.matricula)
        )
        if user is not None:
            school_ids = InstrutorService._visible_school_ids_for(user)
            if school_ids == []:
                return db.paginate(select(Instrutor).where(db.false()), page=page, per_page=per_page)
            if school_ids is not None:
                stmt = stmt.where(UserSchool.school_id.in_(school_ids))
        
        if search_term:
            like_term = f"%{search_term}%"
            stmt = stmt.where(
                or_(
                    User.nome_completo.ilike(like_term),
                    User.matricula.ilike(like_term)
                )
            )

        return db.paginate(stmt, page=page, per_page=per_page, error_out=False)
    
    @staticmethod
    def update_profile_picture(instrutor_id: int, file):
        """Atualiza a foto de perfil de um instrutor."""
        instrutor = db.session.get(Instrutor, instrutor_id)
        if not instrutor:
            return False, "Instrutor não encontrado."

        if file:
            # Remove a foto antiga se não for a padrão
            if instrutor.foto_perfil and instrutor.foto_perfil != 'default.png':
                old_path = os.path.join(current_app.static_folder, 'uploads', 'profile_pics', instrutor.foto_perfil)
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except Exception as e:
                        current_app.logger.error(f"Não foi possível remover a foto antiga do instrutor: {e}")

            # Salva a nova foto
            filename, msg = _save_profile_picture(file)
            if filename:
                instrutor.foto_perfil = filename
                return True, "Foto de perfil atualizada com sucesso."
            else:
                return False, msg
        return False, "Nenhum arquivo de imagem fornecido."

    @staticmethod
    def _find_user_by_email_or_username(email: str):
        email = (email or '').strip()
        if not email:
            return None
        return db.session.scalar(select(User).where(User.email == email))

    @staticmethod
    def _ensure_user_school(user_id: int, school_id: int, role: str = 'instrutor'):
        if not school_id:
            return
        exists = db.session.scalar(
            select(UserSchool.id).where(
                UserSchool.user_id == user_id,
                UserSchool.school_id == school_id
            )
        )
        if not exists:
            db.session.add(UserSchool(user_id=user_id, school_id=school_id, role=role))

    @staticmethod
    def _visible_school_ids_for(user) -> list[int] | None:
        if getattr(user, "role", None) in ("super_admin", "programador"):
            sid = session.get("view_as_school_id")
            
            # --- LINHA CORRIGIDA ---
            # Se 'sid' for None (admin não está personificando), retorna [] (lista vazia)
            # em vez de None. Isso força o 'get_all_instrutores' a não retornar
            # nada, corrigindo o vazamento de dados.
            return [int(sid)] if sid else []
            # --- FIM DA CORREÇÃO ---

        ids = [us.school_id for us in getattr(user, "user_schools", [])]
        return ids or []

    @staticmethod
    def create_full_instrutor(data, school_id):
        try:
            matricula = normalize_matricula(data.get('matricula'))
            email = (data.get('email') or '').strip().lower()
            password = (data.get('password') or '').strip()
            nome_completo = normalize_name(data.get('nome_completo'))
            nome_de_guerra = normalize_name(data.get('nome_de_guerra'))
            
            posto = data.get('posto_graduacao')
            if posto == 'Outro':
                posto = data.get('posto_graduacao_outro')

            telefone = (data.get('telefone') or '').strip() or None
            is_rr = data.get('is_rr', False)

            if not matricula:
                return False, "Matrícula inválida. Use apenas números e no máximo 7 dígitos."
            if not email:
                return False, "O campo E-mail é obrigatório."
            if not password:
                return False, "O campo Senha é obrigatório."

            if db.session.scalar(select(User.id).where(User.matricula == matricula)):
                return False, f"A Matrícula '{matricula}' já está em uso por outro usuário."
            if db.session.scalar(select(User.id).where(User.email == email)):
                return False, f"O e-mail '{email}' já está em uso por outro usuário."

            user = User(
                email=email,
                username=email,
                role='instrutor',
                nome_completo=nome_completo or None,
                nome_de_guerra=nome_de_guerra or None,
                matricula=matricula,
                posto_graduacao=posto,
                is_active=True
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()

            instrutor = Instrutor(
                user_id=user.id,
                school_id=school_id,
                telefone=telefone,
                is_rr=is_rr
            )
            db.session.add(instrutor)

            if school_id:
                InstrutorService._ensure_user_school(user.id, int(school_id), role='instrutor')

            db.session.commit()
            return True, "Instrutor cadastrado com sucesso!"

        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f"Erro de Integridade Inesperado: {getattr(e, 'orig', e)}")
            return False, "Erro de integridade da base de dados. Verifique os dados e tente novamente."
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Erro geral ao criar instrutor")
            return False, "Ocorreu um erro inesperado ao criar o instrutor."

    @staticmethod
    def create_profile_for_user(user_id: int, data: dict):
        user = db.session.get(User, user_id)
        if not user:
            return False, "Usuário não encontrado."
        if getattr(user, "instrutor_profile", None):
            return False, "Este usuário já possui um perfil de instrutor."

        try:
            posto = data.get('posto_graduacao')
            if posto == 'Outro':
                posto = data.get('posto_graduacao_outro')
            
            telefone = (data.get('telefone') or '').strip() or None
            is_rr = data.get('is_rr', False)

            user.posto_graduacao = posto

            new_profile = Instrutor(
                user_id=user_id,
                telefone=telefone,
                is_rr=is_rr
            )
            db.session.add(new_profile)
            db.session.commit()
            return True, "Perfil de instrutor criado com sucesso."

        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao criar perfil de instrutor para usuário existente")
            return False, "Ocorreu um erro inesperado ao salvar o perfil."

    @staticmethod
    def get_instrutor_by_id(instrutor_id: int):
        return db.session.get(Instrutor, instrutor_id)

    @staticmethod
    def update_instrutor(instrutor_id: int, data: dict):
        instrutor = db.session.get(Instrutor, instrutor_id)
        if not instrutor:
            return False, "Instrutor não encontrado."
        try:
            nome_completo = normalize_name(data.get('nome_completo'))
            nome_de_guerra = normalize_name(data.get('nome_de_guerra'))
            
            email = (data.get('email') or '').strip().lower()
            telefone = (data.get('telefone') or '').strip()

            posto = data.get('posto_graduacao')
            if posto == 'Outro':
                posto = data.get('posto_graduacao_outro')

            is_rr = data.get('is_rr', False)

            user = db.session.get(User, instrutor.user_id)
            if user:
                if nome_completo: user.nome_completo = nome_completo
                if nome_de_guerra: user.nome_de_guerra = nome_de_guerra
                if email and user.email != email:
                    exists = db.session.scalar(select(User.id).where(User.email == email, User.id != user.id))
                    if exists:
                        raise IntegrityError("O e-mail fornecido já está em uso.", params=None, orig=None)
                    user.email = email
                if posto:
                    user.posto_graduacao = posto

            instrutor.telefone = (telefone or None)
            instrutor.is_rr = is_rr

            db.session.commit()
            return True, "Instrutor atualizado com sucesso."
        except IntegrityError as e:
            db.session.rollback()
            msg = getattr(e, "orig", None) or "Erro de integridade. Verifique se o e-mail já está em uso."
            return False, str(msg)
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Erro ao atualizar instrutor")
            return False, f"Erro ao atualizar instrutor: {str(e)}"

    @staticmethod
    def delete_instrutor(instrutor_id: int):
        instrutor = db.session.get(Instrutor, instrutor_id)
        if not instrutor:
            return False, "Instrutor não encontrado."

        try:
            user_a_deletar = instrutor.user
            if user_a_deletar:
                db.session.delete(user_a_deletar)
            else:
                db.session.delete(instrutor)
            db.session.commit()
            return True, "Instrutor e usuário vinculado foram excluídos com sucesso."
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao excluir instrutor: {e}")
            return False, f"Erro ao excluir instrutor: {str(e)}"