# backend/services/user_service.py

from flask import current_app, session
from flask_login import current_user
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..models.database import db
from ..models.user import User
from ..models.user_school import UserSchool
from utils.normalizer import normalize_matricula

class UserService:

    # ... (pre_register_user e batch_pre_register_users mantidos, 
    # pois eles já escreviam em UserSchool corretamente, apenas verifique se eles 
    # não estão gravando lixo no user.role global desnecessariamente) ...
    
    # ATUALIZADO
    @staticmethod
    def pre_register_user(data, school_id):
        matricula = normalize_matricula(data.get('matricula'))
        role = (data.get('role') or '').strip()

        if not matricula or not role:
            return False, "Matrícula e Função são obrigatórios."
        if not school_id:
            return False, "A escola é obrigatória."

        existing_user = db.session.scalar(select(User).filter_by(matricula=matricula))

        if existing_user:
            # Verifica se já existe vínculo
            existing_link = db.session.scalar(
                select(UserSchool).filter_by(user_id=existing_user.id, school_id=school_id)
            )
            if existing_link:
                return False, f"O usuário {matricula} já está vinculado a esta escola."
            
            try:
                # CRIA APENAS O VÍNCULO, NÃO MUDA O CARGO GLOBAL SE ELE JÁ TIVER UM
                new_assignment = UserSchool(user_id=existing_user.id, school_id=school_id, role=role)
                db.session.add(new_assignment)
                db.session.commit()
                return True, f"Usuário {matricula} vinculado a esta escola como {role}."
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Erro ao vincular: {e}")
                return False, "Erro ao vincular."
        
        try:
            # Cria usuário. Define role global como 'aluno' por segurança, 
            # a permissão real virá do UserSchool.
            new_user = User(matricula=matricula, role='aluno', is_active=False)
            db.session.add(new_user)
            db.session.flush()
            
            db.session.add(UserSchool(user_id=new_user.id, school_id=school_id, role=role))
            db.session.commit()
            return True, f"Usuário {matricula} criado e vinculado como {role}."
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro no pré-cadastro: {e}")
            return False, "Erro ao criar usuário."

    # NOVA FUNÇÃO DE UTILIDADE SOLICITADA
    @staticmethod
    def set_user_role_for_school(user_id, school_id, new_role):
        """
        Define o cargo de um usuário em uma escola específica.
        Substitui a lógica antiga de alterar user.role diretamente.
        """
        user = db.session.get(User, user_id)
        if not user:
            return False, "Usuário não encontrado."
            
        # Proteção: não rebaixar Programador via interface comum
        if user.role == User.ROLE_PROGRAMADOR:
             return False, "Não é possível alterar cargo de Programador via escola."

        # Busca ou cria o vínculo
        user_school = db.session.scalar(
            select(UserSchool).filter_by(user_id=user_id, school_id=school_id)
        )

        try:
            if user_school:
                user_school.role = new_role
            else:
                user_school = UserSchool(user_id=user_id, school_id=school_id, role=new_role)
                db.session.add(user_school)
            
            # ATENÇÃO: Compatibilidade Reversa / Limpeza
            # Se o usuário tinha um cargo global "admin_X" e agora estamos setando
            # especificamente na escola, podemos querer limpar o global para 'aluno'
            # para evitar conflitos futuros, MAS somente se for seguro.
            # Por enquanto, mantemos o global intacto para não quebrar outras escolas
            # até rodarmos a migração completa.
            
            db.session.commit()
            return True, "Permissão atualizada na escola com sucesso."
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao setar role: {e}")
            return False, "Erro de banco de dados."

    # Alias para compatibilidade com código existente que chamava assign_school_role
    assign_school_role = set_user_role_for_school

    @staticmethod
    def get_current_school_id():
        """
        Lógica inalterada (já fornecida corretamente no upload), 
        essencial para os decorators saberem onde estamos.
        """
        if not current_user.is_authenticated:
            return None

        if getattr(current_user, 'role', '') in ['super_admin', 'programador']:
            view_as = session.get('view_as_school_id')
            if view_as: return int(view_as)

        active_id = session.get('active_school_id')
        if active_id:
            try:
                active_id_int = int(active_id)
                # Verifica se o vínculo ainda existe no banco
                has_link = db.session.scalar(
                    select(UserSchool.school_id).where(
                        UserSchool.user_id == current_user.id,
                        UserSchool.school_id == active_id_int
                    )
                )
                if has_link: return active_id_int
                else: session.pop('active_school_id', None)
            except Exception: pass

        all_links = db.session.execute(
            select(UserSchool).where(UserSchool.user_id == current_user.id)
        ).scalars().all()

        if len(all_links) == 1:
            chosen_id = all_links[0].school_id
            session['active_school_id'] = chosen_id
            return chosen_id
            
        return None
        
    # Demais métodos (delete_user_by_id, remove_school_role) mantidos...