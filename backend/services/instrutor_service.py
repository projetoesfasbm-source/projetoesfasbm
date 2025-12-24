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

# Importação para garantir o contexto da sessão (Correção do Bug)
from .user_service import UserService

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
        Lista instrutores BLINDANDO o perfil pela escola atual (Conceito Matrícula 2).
        """
        # Pega a escola da sessão de forma segura
        active_school_id = UserService.get_current_school_id()
        
        if not active_school_id:
            return db.paginate(select(Instrutor).where(db.false()), page=page, per_page=per_page)

        stmt = (
            select(Instrutor)
            .join(User, Instrutor.user_id == User.id)
            .where(
                User.is_active.is_(True),
                User.role == 'instrutor',
                # AQUI ESTÁ A CORREÇÃO CRUCIAL:
                # Filtra especificamente o perfil de instrutor criado para ESTA escola.
                # Isso ignora perfis do mesmo usuário em outras escolas.
                Instrutor.school_id == active_school_id
            )
            .options(joinedload(Instrutor.user))
            .order_by(User.nome_completo, User.matricula)
        )

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
    def get_all_instrutores_sem_paginacao(user=None):
        """
        Retorna TODOS os instrutores ativos visíveis para a escola atual.
        """
        active_school_id = UserService.get_current_school_id()
        if not active_school_id:
            return []
            
        stmt = (
            select(Instrutor)
            .join(User, Instrutor.user_id == User.id)
            .where(
                User.is_active.is_(True),
                User.role == 'instrutor',
                # CORREÇÃO DE BLINDAGEM AQUI TAMBÉM
                Instrutor.school_id == active_school_id
            )
            .options(joinedload(Instrutor.user))
            .order_by(User.nome_completo)
        )
        
        return db.session.scalars(stmt).unique().all()
    
    @staticmethod
    def update_profile_picture(instrutor_id: int, file):
        instrutor = db.session.get(Instrutor, instrutor_id)
        if not instrutor:
            return False, "Instrutor não encontrado."

        if file:
            if instrutor.foto_perfil and instrutor.foto_perfil != 'default.png':
                old_path = os.path.join(current_app.static_folder, 'uploads', 'profile_pics', instrutor.foto_perfil)
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except Exception as e:
                        current_app.logger.error(f"Não foi possível remover a foto antiga: {e}")

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
                return False, "Matrícula inválida."
            if not email:
                return False, "O campo E-mail é obrigatório."
            if not password:
                return False, "O campo Senha é obrigatório."

            existing_user = db.session.scalar(select(User).where(User.matricula == matricula))
            
            if existing_user:
                if existing_user.email and existing_user.email != email:
                    return False, f"A Matrícula '{matricula}' já existe, mas o e-mail não confere."

                # Verifica se já existe perfil PARA ESTA ESCOLA ESPECÍFICA
                # (Garante que não criamos duplicatas dentro da mesma escola)
                existing_profile = db.session.scalar(select(Instrutor).where(
                    Instrutor.user_id == existing_user.id,
                    Instrutor.school_id == school_id
                ))

                if not existing_profile:
                    new_profile = Instrutor(
                        user_id=existing_user.id,
                        school_id=school_id,
                        telefone=telefone,
                        is_rr=is_rr
                    )
                    db.session.add(new_profile)
                
                InstrutorService._ensure_user_school(existing_user.id, int(school_id), role='instrutor')
                
                db.session.commit()
                return True, f"Instrutor {existing_user.nome_completo} vinculado à esta escola com sucesso!"
            
            if db.session.scalar(select(User.id).where(User.email == email)):
                return False, f"O e-mail '{email}' já está em uso."

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
            current_app.logger.error(f"Erro de Integridade: {e}")
            return False, "Erro de integridade (dados duplicados)."
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Erro ao criar instrutor")
            return False, "Erro inesperado ao criar instrutor."

    @staticmethod
    def create_profile_for_user(user_id: int, data: dict):
        """
        Cria um perfil de instrutor vinculado à ESCOLA ATUAL.
        """
        school_id = UserService.get_current_school_id()
        if not school_id:
            return False, "Escola não selecionada na sessão."

        user = db.session.get(User, user_id)
        if not user:
            return False, "Usuário não encontrado."
        
        # Verifica se já existe perfil NESTA escola
        existing = db.session.scalar(select(Instrutor).where(
            Instrutor.user_id == user_id, 
            Instrutor.school_id == school_id
        ))
        if existing:
            return False, "Este usuário já possui um perfil de instrutor nesta escola."

        try:
            posto = data.get('posto_graduacao')
            if posto == 'Outro':
                posto = data.get('posto_graduacao_outro')
            
            telefone = (data.get('telefone') or '').strip() or None
            is_rr = data.get('is_rr', False)

            user.posto_graduacao = posto

            new_profile = Instrutor(
                user_id=user_id,
                school_id=school_id, # VÍNCULO FORTE
                telefone=telefone,
                is_rr=is_rr
            )
            db.session.add(new_profile)
            
            InstrutorService._ensure_user_school(user_id, school_id)
            
            db.session.commit()
            return True, "Perfil de instrutor criado com sucesso."

        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao criar perfil de instrutor")
            return False, "Erro ao salvar o perfil."

    @staticmethod
    def get_instrutor_by_id(instrutor_id: int):
        # Segurança: Garante que só retorna se pertencer à escola atual
        active_school = UserService.get_current_school_id()
        instrutor = db.session.get(Instrutor, instrutor_id)
        
        # Se instrutor existe e pertence à escola ativa, retorna.
        if instrutor and instrutor.school_id == active_school:
            return instrutor
        return None

    @staticmethod
    def update_instrutor(instrutor_id: int, data: dict):
        instrutor = db.session.get(Instrutor, instrutor_id)
        if not instrutor:
            return False, "Instrutor não encontrado."
        
        # Proteção extra: só edita se for da escola atual
        if instrutor.school_id != UserService.get_current_school_id():
            return False, "Permissão negada: Este instrutor pertence a outra escola."

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
                        raise IntegrityError("E-mail em uso.", params=None, orig=None)
                    user.email = email
                if posto:
                    user.posto_graduacao = posto

            instrutor.telefone = (telefone or None)
            instrutor.is_rr = is_rr

            db.session.commit()
            return True, "Instrutor atualizado com sucesso."
        except IntegrityError as e:
            db.session.rollback()
            return False, "O e-mail fornecido já está em uso."
        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao atualizar: {str(e)}"

    @staticmethod
    def delete_instrutor(instrutor_id: int):
        instrutor = db.session.get(Instrutor, instrutor_id)
        if not instrutor:
            return False, "Instrutor não encontrado."
        
        if instrutor.school_id != UserService.get_current_school_id():
            return False, "Permissão negada."

        try:
            # Se o usuário tem perfis em OUTRAS escolas, deleta só este perfil (Instrutor)
            # Se só tem este, poderia deletar o User todo, mas por segurança deletamos apenas o perfil e vínculo
            db.session.delete(instrutor)
            
            # Remove o vínculo user_school desta escola também
            link = db.session.scalar(select(UserSchool).where(
                UserSchool.user_id==instrutor.user_id, 
                UserSchool.school_id==instrutor.school_id
            ))
            if link:
                db.session.delete(link)
            
            db.session.commit()
            return True, "Instrutor removido desta escola com sucesso."
        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao excluir: {str(e)}"