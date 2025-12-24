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

# Importação para garantir o contexto da sessão
from .user_service import UserService

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def _save_profile_picture(file):
    if not file: return None, "Nenhum arquivo enviado."
    file.stream.seek(0)
    if not allowed_file(file.filename, file.stream, ALLOWED_EXTENSIONS):
        return None, "Tipo de arquivo não permitido."
    try:
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4()}.{ext}"
        upload_folder = os.path.join(current_app.static_folder, 'uploads', 'profile_pics')
        os.makedirs(upload_folder, exist_ok=True)
        file.stream.seek(0)
        file.save(os.path.join(upload_folder, unique_filename))
        return unique_filename, "Salvo com sucesso"
    except Exception as e:
        current_app.logger.error(f"Erro foto: {e}")
        return None, "Erro ao salvar imagem."

class InstrutorService:
    @staticmethod
    def get_all_instrutores(user=None, search_term=None, page=1, per_page=15):
        """
        Lista instrutores BLINDANDO o perfil pela escola atual.
        """
        active_school_id = UserService.get_current_school_id()
        
        if not active_school_id:
            return db.paginate(select(Instrutor).where(db.false()), page=page, per_page=per_page)

        stmt = (
            select(Instrutor)
            .join(User, Instrutor.user_id == User.id)
            .where(
                User.is_active.is_(True),
                User.role == 'instrutor',
                # AQUI ESTÁ A CORREÇÃO "MATRICULA 2":
                # Só traz o perfil de instrutor que foi criado PARA ESTA ESCOLA.
                # O perfil da outra escola será ignorado.
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
        active_school_id = UserService.get_current_school_id()
        if not active_school_id: return []
            
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
        if not instrutor: return False, "Instrutor não encontrado."
        if file:
            if instrutor.foto_perfil and instrutor.foto_perfil != 'default.png':
                try: os.remove(os.path.join(current_app.static_folder, 'uploads', 'profile_pics', instrutor.foto_perfil))
                except: pass
            filename, msg = _save_profile_picture(file)
            if filename:
                instrutor.foto_perfil = filename
                return True, "Foto atualizada."
            return False, msg
        return False, "Sem arquivo."

    @staticmethod
    def _ensure_user_school(user_id: int, school_id: int, role: str = 'instrutor'):
        if not school_id: return
        exists = db.session.scalar(select(UserSchool.id).where(UserSchool.user_id==user_id, UserSchool.school_id==school_id))
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
            if posto == 'Outro': posto = data.get('posto_graduacao_outro')
            telefone = (data.get('telefone') or '').strip() or None
            is_rr = data.get('is_rr', False)

            if not matricula or not email or not password:
                return False, "Dados obrigatórios faltando."

            existing_user = db.session.scalar(select(User).where(User.matricula == matricula))
            
            if existing_user:
                if existing_user.email and existing_user.email != email:
                    return False, "Matrícula já existe com outro e-mail."
                
                # Verifica se já existe perfil PARA ESTA ESCOLA ESPECÍFICA
                existing_profile = db.session.scalar(select(Instrutor).where(
                    Instrutor.user_id == existing_user.id,
                    Instrutor.school_id == school_id
                ))

                if not existing_profile:
                    new_profile = Instrutor(user_id=existing_user.id, school_id=school_id, telefone=telefone, is_rr=is_rr)
                    db.session.add(new_profile)
                
                InstrutorService._ensure_user_school(existing_user.id, int(school_id), role='instrutor')
                db.session.commit()
                return True, f"Instrutor vinculado a esta escola com sucesso!"
            
            if db.session.scalar(select(User.id).where(User.email == email)):
                return False, "E-mail em uso."

            user = User(email=email, username=email, role='instrutor', nome_completo=nome_completo, nome_de_guerra=nome_de_guerra, matricula=matricula, posto_graduacao=posto, is_active=True)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()

            instrutor = Instrutor(user_id=user.id, school_id=school_id, telefone=telefone, is_rr=is_rr)
            db.session.add(instrutor)
            if school_id: InstrutorService._ensure_user_school(user.id, int(school_id), role='instrutor')

            db.session.commit()
            return True, "Instrutor criado."
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro create_full_instrutor: {e}")
            return False, "Erro interno."

    @staticmethod
    def create_profile_for_user(user_id: int, data: dict):
        # Cria perfil vinculado à ESCOLA ATUAL
        school_id = UserService.get_current_school_id()
        if not school_id: return False, "Escola não selecionada."

        user = db.session.get(User, user_id)
        if not user: return False, "Usuário não encontrado."
        
        # Verifica duplicidade NA MESMA ESCOLA
        existing = db.session.scalar(select(Instrutor).where(Instrutor.user_id==user_id, Instrutor.school_id==school_id))
        if existing: return False, "Já existe perfil nesta escola."

        try:
            posto = data.get('posto_graduacao')
            if posto == 'Outro': posto = data.get('posto_graduacao_outro')
            user.posto_graduacao = posto
            
            new_profile = Instrutor(
                user_id=user_id, 
                school_id=school_id, # VÍNCULO FORTE
                telefone=data.get('telefone'), 
                is_rr=data.get('is_rr', False)
            )
            db.session.add(new_profile)
            
            # Garante user_school também
            InstrutorService._ensure_user_school(user_id, school_id)
            
            db.session.commit()
            return True, "Perfil criado."
        except Exception:
            db.session.rollback()
            return False, "Erro ao salvar."

    @staticmethod
    def get_instrutor_by_id(instrutor_id: int):
        # Garante que só retorna se pertencer à escola atual (segurança extra)
        active_school = UserService.get_current_school_id()
        instrutor = db.session.get(Instrutor, instrutor_id)
        if instrutor and instrutor.school_id == active_school:
            return instrutor
        return None

    @staticmethod
    def update_instrutor(instrutor_id: int, data: dict):
        instrutor = db.session.get(Instrutor, instrutor_id)
        if not instrutor: return False, "Não encontrado."
        
        # Proteção: só edita se for da escola atual
        if instrutor.school_id != UserService.get_current_school_id():
            return False, "Permissão negada: Instrutor de outra escola."

        try:
            user = db.session.get(User, instrutor.user_id)
            if user:
                user.nome_completo = normalize_name(data.get('nome_completo'))
                user.nome_de_guerra = normalize_name(data.get('nome_de_guerra'))
                email = (data.get('email') or '').strip().lower()
                if email and user.email != email:
                    if db.session.scalar(select(User.id).where(User.email == email, User.id != user.id)):
                        return False, "E-mail em uso."
                    user.email = email
                
                posto = data.get('posto_graduacao')
                user.posto_graduacao = data.get('posto_graduacao_outro') if posto == 'Outro' else posto

            instrutor.telefone = data.get('telefone')
            instrutor.is_rr = data.get('is_rr', False)
            db.session.commit()
            return True, "Atualizado."
        except Exception as e:
            db.session.rollback()
            return False, f"Erro: {e}"

    @staticmethod
    def delete_instrutor(instrutor_id: int):
        instrutor = db.session.get(Instrutor, instrutor_id)
        if not instrutor: return False, "Não encontrado."
        
        if instrutor.school_id != UserService.get_current_school_id():
            return False, "Permissão negada."

        try:
            # Se o usuário tem perfis em OUTRAS escolas, deleta só este perfil (Instrutor)
            # Se só tem este, deleta o User todo (opcional, aqui deletamos o perfil para segurança)
            db.session.delete(instrutor)
            
            # Remove o vínculo user_school desta escola também
            link = db.session.scalar(select(UserSchool).where(
                UserSchool.user_id==instrutor.user_id, 
                UserSchool.school_id==instrutor.school_id
            ))
            if link: db.session.delete(link)
            
            db.session.commit()
            return True, "Instrutor removido desta escola."
        except Exception as e:
            db.session.rollback()
            return False, f"Erro: {e}"