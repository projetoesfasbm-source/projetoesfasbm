# backend/services/diario_service.py
import os
import base64
import uuid
import shutil
from datetime import datetime
from flask import current_app, session
from ..models.database import db
from ..models.diario_classe import DiarioClasse
from ..models.horario import Horario
from ..models.instrutor import Instrutor
from ..models.turma import Turma
from ..models.semana import Semana
from ..models.disciplina import Disciplina
from sqlalchemy import select, and_, or_

class DiarioService:
    
    @staticmethod
    def get_current_instrutor(user_id):
        school_id = session.get('active_school_id')
        query = select(Instrutor).where(Instrutor.user_id == user_id)
        if school_id:
            try:
                query = query.where(Instrutor.school_id == int(school_id))
            except (ValueError, TypeError):
                pass
        return db.session.scalars(query).first()

    @staticmethod
    def get_diarios_pendentes(school_id, user_id=None, turma_id=None, disciplina_id=None):
        """
        Busca diários pendentes.
        - Se user_id for fornecido: Filtra apenas aulas daquele instrutor.
        - Se user_id for None: Traz TUDO da escola (Modo Admin).
        - Filtra também por Turma e Disciplina se fornecidos.
        """
        stmt = (
            select(DiarioClasse)
            .join(Turma, DiarioClasse.turma_id == Turma.id)
            .join(Horario, and_(
                Horario.pelotao == Turma.nome,
                Horario.disciplina_id == DiarioClasse.disciplina_id,
                Horario.periodo == DiarioClasse.periodo
            ))
            .join(Semana, Horario.semana_id == Semana.id)
            .where(
                # Garante que pertence à escola atual (via Turma)
                Turma.school_id == school_id,
                DiarioClasse.status == 'pendente',
                DiarioClasse.conteudo_ministrado != None,
                DiarioClasse.conteudo_ministrado != '',
                Semana.data_inicio <= DiarioClasse.data_aula,
                Semana.data_fim >= DiarioClasse.data_aula
            )
            .order_by(DiarioClasse.data_aula.desc())
        )

        # Lógica de Permissão (Instrutor vs Admin)
        if user_id:
            instrutor = DiarioService.get_current_instrutor(user_id)
            if instrutor:
                stmt = stmt.where(or_(
                    Horario.instrutor_id == instrutor.id,
                    Horario.instrutor_id_2 == instrutor.id
                ))
            else:
                return [] # Se passou ID mas não achou perfil, não retorna nada

        # Filtros Opcionais
        if turma_id:
            stmt = stmt.where(DiarioClasse.turma_id == turma_id)
        
        if disciplina_id:
            stmt = stmt.where(DiarioClasse.disciplina_id == disciplina_id)
        
        return db.session.scalars(stmt.distinct()).all()

    @staticmethod
    def get_filtros_disponiveis(school_id, user_id=None):
        """
        Retorna as Turmas e Disciplinas que possuem pendências,
        para preencher os dropdowns de filtro de forma inteligente.
        """
        # Base Query
        base_query = (
            select(DiarioClasse)
            .join(Turma, DiarioClasse.turma_id == Turma.id)
            .join(Horario, and_(
                Horario.pelotao == Turma.nome,
                Horario.disciplina_id == DiarioClasse.disciplina_id,
                Horario.periodo == DiarioClasse.periodo
            ))
            .join(Semana, Horario.semana_id == Semana.id)
            .where(
                Turma.school_id == school_id,
                DiarioClasse.status == 'pendente',
                DiarioClasse.conteudo_ministrado != None,
                DiarioClasse.conteudo_ministrado != '',
                Semana.data_inicio <= DiarioClasse.data_aula,
                Semana.data_fim >= DiarioClasse.data_aula
            )
        )

        if user_id:
            instrutor = DiarioService.get_current_instrutor(user_id)
            if instrutor:
                base_query = base_query.where(or_(
                    Horario.instrutor_id == instrutor.id,
                    Horario.instrutor_id_2 == instrutor.id
                ))
            else:
                return [], []

        # Busca Turmas Distintas
        stmt_turmas = select(Turma).join(base_query.subquery()).distinct().order_by(Turma.nome)
        turmas = db.session.scalars(stmt_turmas).all()

        # Busca Disciplinas Distintas
        stmt_disc = select(Disciplina).join(base_query.subquery()).distinct().order_by(Disciplina.materia)
        disciplinas = db.session.scalars(stmt_disc).all()

        return turmas, disciplinas

    @staticmethod
    def get_diario_para_assinatura(diario_id, user_id):
        # Para assinar, precisamos validar se quem está assinando é o instrutor da aula,
        # OU se é um Admin fazendo uma validação forçada (regra de negócio a decidir).
        # Por segurança, mantemos que APENAS o instrutor responsável assina seu nome,
        # ou o Admin se tiver permissão explícita (aqui assumimos fluxo normal).
        
        instrutor = DiarioService.get_current_instrutor(user_id)
        if not instrutor:
            # Se for admin tentando assinar, precisaria de lógica extra aqui.
            # Por enquanto, mantemos a exigência de ser o instrutor da aula.
            return None, None

        stmt = (
            select(DiarioClasse)
            .join(Turma, DiarioClasse.turma_id == Turma.id)
            .join(Horario, and_(
                Horario.pelotao == Turma.nome,
                Horario.disciplina_id == DiarioClasse.disciplina_id,
                Horario.periodo == DiarioClasse.periodo
            ))
            .join(Semana, Horario.semana_id == Semana.id)
            .where(
                DiarioClasse.id == diario_id,
                or_(
                    Horario.instrutor_id == instrutor.id,
                    Horario.instrutor_id_2 == instrutor.id
                ),
                Semana.data_inicio <= DiarioClasse.data_aula,
                Semana.data_fim >= DiarioClasse.data_aula
            )
        )
        return db.session.scalars(stmt).first(), instrutor

    @staticmethod
    def assinar_diario(diario_id, user_id, tipo_assinatura, dados_assinatura=None, salvar_padrao=False):
        diario, instrutor = DiarioService.get_diario_para_assinatura(diario_id, user_id)
        if not diario:
            return False, "Permissão negada ou diário não encontrado."

        base_path = os.path.join(current_app.root_path, '..', 'static')
        upload_folder = os.path.join(base_path, 'uploads', 'signatures')
        os.makedirs(upload_folder, exist_ok=True)
        
        filename = f"sig_diario_{diario.id}_{uuid.uuid4().hex[:8]}.png"
        filepath = os.path.join(upload_folder, filename)
        db_path = f"uploads/signatures/{filename}"

        try:
            if tipo_assinatura == 'padrao':
                if not instrutor.assinatura_padrao_path:
                    return False, "Você não possui uma assinatura padrão salva."
                source_path = os.path.join(base_path, instrutor.assinatura_padrao_path)
                if not os.path.exists(source_path):
                    return False, "Arquivo de assinatura padrão não encontrado."
                shutil.copy2(source_path, filepath)

            elif tipo_assinatura == 'canvas':
                if not dados_assinatura: return False, "Assinatura vazia."
                if ',' in dados_assinatura: _, encoded = dados_assinatura.split(',', 1)
                else: encoded = dados_assinatura
                img_data = base64.b64decode(encoded)
                with open(filepath, 'wb') as f: f.write(img_data)

            elif tipo_assinatura == 'upload':
                if not dados_assinatura: return False, "Arquivo não fornecido."
                dados_assinatura.save(filepath)

            else: return False, "Método inválido."

            diario.assinatura_path = db_path
            diario.status = 'assinado'
            diario.data_assinatura = datetime.now()
            diario.instrutor_assinante_id = user_id

            if salvar_padrao and tipo_assinatura in ['canvas', 'upload']:
                default_filename = f"default_sig_instrutor_{instrutor.id}.png"
                default_filepath = os.path.join(upload_folder, default_filename)
                shutil.copy2(filepath, default_filepath)
                instrutor.assinatura_padrao_path = f"uploads/signatures/{default_filename}"

            db.session.commit()
            return True, "Diário assinado com sucesso."

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao assinar: {e}")
            return False, f"Erro técnico: {str(e)}"