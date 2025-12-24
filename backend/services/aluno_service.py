# backend/services/aluno_service.py

import os
import uuid
from datetime import datetime
from flask import current_app, session
from werkzeug.utils import secure_filename
from sqlalchemy import select, or_
from sqlalchemy.orm import joinedload

from ..models.database import db
from ..models.aluno import Aluno
from ..models.user import User
from ..models.turma import Turma
from ..models.historico import HistoricoAluno
from ..models.user_school import UserSchool
from utils.image_utils import allowed_file
from utils.normalizer import normalize_name
from .user_service import UserService

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def _save_profile_picture(file):
    # (Mantido igual ao anterior, omitido para brevidade mas deve estar no arquivo final)
    if not file: return None, "Nenhum arquivo enviado."
    file.stream.seek(0)
    if not allowed_file(file.filename, file.stream, ALLOWED_EXTENSIONS): return None, "Tipo inválido."
    try:
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower()
        uid = f"{uuid.uuid4()}.{ext}"
        path = os.path.join(current_app.static_folder, 'uploads', 'profile_pics', uid)
        file.stream.seek(0)
        file.save(path)
        return uid, "Sucesso"
    except: return None, "Erro ao salvar."

class AlunoService:
    @staticmethod
    def get_all_alunos(user, nome_turma=None, search_term=None, page=1, per_page=15):
        active_school_id = UserService.get_current_school_id()
        if not active_school_id:
            return db.paginate(select(Aluno).where(db.false()), page=page, per_page=per_page)

        stmt = (
            select(Aluno)
            .join(User, Aluno.user_id == User.id)
            .join(Turma, Aluno.turma_id == Turma.id) # JOIN CRUCIAL
            .where(
                User.is_active.is_(True),
                User.role == 'aluno',
                # CORREÇÃO "MATRÍCULA 2": Filtra pela escola da TURMA do aluno
                Turma.school_id == active_school_id
            )
            .options(joinedload(Aluno.user), joinedload(Aluno.turma))
            .order_by(User.nome_completo, User.matricula)
        )

        if nome_turma:
            stmt = stmt.where(Turma.nome == nome_turma)
        
        if search_term:
            like = f"%{search_term}%"
            stmt = stmt.where(or_(User.nome_completo.ilike(like), User.matricula.ilike(like)))

        return db.paginate(stmt, page=page, per_page=per_page, error_out=False)

    @staticmethod
    def get_aluno_by_id(aluno_id: int):
        active_school = UserService.get_current_school_id()
        aluno = db.session.get(Aluno, aluno_id)
        # Segurança: só retorna se a turma do aluno for desta escola
        if aluno and aluno.turma and aluno.turma.school_id == active_school:
            return aluno
        return None
        
    @staticmethod
    def update_profile_picture(aluno_id: int, file):
        aluno = AlunoService.get_aluno_by_id(aluno_id)
        if not aluno: return False, "Aluno não encontrado ou de outra escola."
        
        if file:
            if aluno.foto_perfil and aluno.foto_perfil != 'default.png':
                try: os.remove(os.path.join(current_app.static_folder, 'uploads', 'profile_pics', aluno.foto_perfil))
                except: pass
            fname, msg = _save_profile_picture(file)
            if fname:
                aluno.foto_perfil = fname
                return True, "Foto atualizada."
            return False, msg
        return False, "Sem arquivo."

    @staticmethod
    def update_aluno(aluno_id: int, data: dict):
        aluno = AlunoService.get_aluno_by_id(aluno_id)
        if not aluno: return False, "Aluno não encontrado."

        nome = normalize_name(data.get('nome_completo'))
        email = (data.get('email') or '').strip()
        opm = (data.get('opm') or '').strip()
        turma_id = data.get('turma_id')

        if not all([nome, opm, email, turma_id]): return False, "Campos obrigatórios."

        try:
            # Verifica se a nova turma pertence à escola atual
            new_turma = db.session.get(Turma, turma_id)
            if not new_turma or new_turma.school_id != UserService.get_current_school_id():
                return False, "Turma inválida."

            if aluno.user and aluno.user.email != email:
                if db.session.scalar(select(User.id).where(User.email == email, User.id != aluno.user.id)):
                    return False, "E-mail em uso."

            if aluno.user:
                aluno.user.nome_completo = nome
                aluno.user.email = email
                posto = data.get('posto_graduacao')
                aluno.user.posto_graduacao = data.get('posto_graduacao_outro') if posto == 'Outro' else posto

            aluno.opm = opm
            aluno.turma_id = int(turma_id)
            db.session.commit()
            return True, "Atualizado."
        except Exception as e:
            db.session.rollback()
            return False, f"Erro: {e}"

    @staticmethod
    def update_funcao_aluno(aluno_id: int, form_data: dict):
        aluno = AlunoService.get_aluno_by_id(aluno_id)
        if not aluno: return False, "Aluno não encontrado."
        try:
            nova = form_data.get('funcao_atual')
            dt = datetime.strptime(form_data.get('data_evento'), '%Y-%m-%d') if form_data.get('data_evento') else datetime.utcnow()
            
            if aluno.funcao_atual and aluno.funcao_atual != nova:
                # Lógica de histórico (simplificada)
                pass 

            if nova and nova != aluno.funcao_atual:
                db.session.add(HistoricoAluno(aluno_id=aluno_id, tipo='Função', descricao=f'Assumiu: {nova}', data_inicio=dt))

            aluno.funcao_atual = nova if nova else None
            db.session.commit()
            return True, "Função atualizada."
        except Exception:
            db.session.rollback()
            return False, "Erro."

    @staticmethod
    def delete_aluno(aluno_id: int):
        aluno = AlunoService.get_aluno_by_id(aluno_id)
        if not aluno: return False, "Não encontrado."
        try:
            if aluno.user: db.session.delete(aluno.user)
            else: db.session.delete(aluno)
            db.session.commit()
            return True, "Excluído."
        except Exception as e:
            db.session.rollback()
            return False, f"Erro: {e}"