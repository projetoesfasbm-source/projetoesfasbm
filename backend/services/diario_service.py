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
from ..models.disciplina import Disciplina
from sqlalchemy import select, and_, or_, distinct

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
    def get_diarios_pendentes(school_id, user_id=None, turma_id=None, disciplina_id=None, status=None):
        """
        Retorna lista simples de diários.
        Usado pelo Admin para listagem geral e auditoria linha-a-linha.
        """
        stmt = (
            select(DiarioClasse)
            .join(Turma, DiarioClasse.turma_id == Turma.id)
            .where(
                Turma.school_id == school_id,
                DiarioClasse.conteudo_ministrado != None,
                DiarioClasse.conteudo_ministrado != ''
            )
        )

        if status:
            stmt = stmt.where(DiarioClasse.status == status)

        if user_id:
            instrutor = DiarioService.get_current_instrutor(user_id)
            if instrutor:
                stmt = stmt.join(Horario, and_(
                    Horario.pelotao == Turma.nome,
                    Horario.disciplina_id == DiarioClasse.disciplina_id,
                    Horario.periodo == DiarioClasse.periodo
                )).where(
                    or_(Horario.instrutor_id == instrutor.id, Horario.instrutor_id_2 == instrutor.id)
                )
            else:
                return []

        if turma_id:
            stmt = stmt.where(DiarioClasse.turma_id == turma_id)
        
        if disciplina_id:
            stmt = stmt.where(DiarioClasse.disciplina_id == disciplina_id)

        stmt = stmt.order_by(DiarioClasse.data_aula.desc(), DiarioClasse.periodo)
        
        return db.session.scalars(stmt.distinct()).all()

    @staticmethod
    def get_diarios_agrupados(school_id, user_id=None, turma_id=None, disciplina_id=None, status=None):
        """
        Retorna lista AGRUPADA de diários (blocos de aulas).
        Usado pelo Instrutor e pelo Relatório de Impressão Oficial.
        """
        stmt = (
            select(DiarioClasse)
            .join(Turma, DiarioClasse.turma_id == Turma.id)
            .where(
                Turma.school_id == school_id,
                DiarioClasse.conteudo_ministrado != None,
                DiarioClasse.conteudo_ministrado != ''
            )
        )

        if status: stmt = stmt.where(DiarioClasse.status == status)

        if user_id:
            instrutor = DiarioService.get_current_instrutor(user_id)
            if instrutor:
                stmt = stmt.join(Horario, and_(
                    Horario.pelotao == Turma.nome,
                    Horario.disciplina_id == DiarioClasse.disciplina_id
                )).where(
                    or_(Horario.instrutor_id == instrutor.id, Horario.instrutor_id_2 == instrutor.id)
                )
            else:
                return []

        if turma_id: stmt = stmt.where(DiarioClasse.turma_id == turma_id)
        if disciplina_id: stmt = stmt.where(DiarioClasse.disciplina_id == disciplina_id)

        stmt = stmt.distinct().order_by(
            DiarioClasse.data_aula.desc(), 
            DiarioClasse.turma_id, 
            DiarioClasse.disciplina_id, 
            DiarioClasse.periodo
        )
        
        raw_diarios = db.session.scalars(stmt).all()

        grouped_diarios = []
        if not raw_diarios: return []

        current_group = [raw_diarios[0]]

        for i in range(1, len(raw_diarios)):
            curr = raw_diarios[i]
            prev = current_group[-1]

            if (curr.data_aula == prev.data_aula and 
                curr.turma_id == prev.turma_id and 
                curr.disciplina_id == prev.disciplina_id):
                current_group.append(curr)
            else:
                grouped_diarios.append(DiarioService._criar_representante_grupo(current_group))
                current_group = [curr]
        
        if current_group:
            grouped_diarios.append(DiarioService._criar_representante_grupo(current_group))

        return grouped_diarios

    @staticmethod
    def _criar_representante_grupo(group_items):
        group_items.sort(key=lambda x: x.periodo or 0)
        
        rep = group_items[0] 
        first_p = group_items[0].periodo
        last_p = group_items[-1].periodo
        
        if first_p is None: 
            rep.periodo_resumo = "Período N/D"
        elif first_p == last_p: 
            rep.periodo_resumo = f"{first_p}º Período"
        else: 
            rep.periodo_resumo = f"{first_p}º a {last_p}º Período"
            
        rep.total_aulas_bloco = len(group_items)
        return rep

    @staticmethod
    def get_filtros_disponiveis(school_id, user_id=None, turma_selected_id=None):
        base_query = select(DiarioClasse).join(Turma).where(Turma.school_id == school_id)
        
        if user_id:
            instrutor = DiarioService.get_current_instrutor(user_id)
            if instrutor:
                base_query = base_query.join(Horario, and_(
                    Horario.pelotao == Turma.nome,
                    Horario.disciplina_id == DiarioClasse.disciplina_id
                )).where(
                    or_(Horario.instrutor_id == instrutor.id, Horario.instrutor_id_2 == instrutor.id)
                )

        stmt_turmas = select(Turma).join(base_query.subquery()).distinct().order_by(Turma.nome)
        turmas = db.session.scalars(stmt_turmas).all()

        disciplina_query = base_query
        if turma_selected_id:
            disciplina_query = disciplina_query.where(DiarioClasse.turma_id == turma_selected_id)

        stmt_disc = select(Disciplina).join(disciplina_query.subquery()).distinct().order_by(Disciplina.materia)
        disciplinas = db.session.scalars(stmt_disc).all()
        
        unique_disciplinas = {d.materia: d for d in disciplinas}.values()
        disciplinas_sorted = sorted(unique_disciplinas, key=lambda x: x.materia)

        return turmas, disciplinas_sorted

    @staticmethod
    def get_diario_para_assinatura(diario_id, user_id):
        instrutor = DiarioService.get_current_instrutor(user_id)
        if not instrutor: return None, None
        
        stmt = select(DiarioClasse).join(Turma).join(Horario, and_(
                Horario.pelotao == Turma.nome,
                Horario.disciplina_id == DiarioClasse.disciplina_id
            )).where(
                DiarioClasse.id == diario_id,
                or_(Horario.instrutor_id == instrutor.id, Horario.instrutor_id_2 == instrutor.id)
            )
        return db.session.scalars(stmt).first(), instrutor

    @staticmethod
    def assinar_diario(diario_id, user_id, tipo_assinatura, dados_assinatura=None, salvar_padrao=False):
        diario_pai, instrutor = DiarioService.get_diario_para_assinatura(diario_id, user_id)
        if not diario_pai:
            return False, "Permissão negada ou diário não encontrado."

        base_path = os.path.join(current_app.root_path, '..', 'static')
        upload_folder = os.path.join(base_path, 'uploads', 'signatures')
        os.makedirs(upload_folder, exist_ok=True)
        
        filename = f"sig_diario_{diario_pai.id}_{uuid.uuid4().hex[:8]}.png"
        filepath = os.path.join(upload_folder, filename)
        db_path = f"uploads/signatures/{filename}"

        try:
            if tipo_assinatura == 'padrao':
                if not instrutor.assinatura_padrao_path: return False, "Assinatura padrão não encontrada."
                src = os.path.join(base_path, instrutor.assinatura_padrao_path)
                if not os.path.exists(src): return False, "Arquivo padrão inexistente."
                shutil.copy2(src, filepath)

            elif tipo_assinatura == 'canvas':
                if not dados_assinatura: return False, "Assinatura vazia."
                header, encoded = dados_assinatura.split(',', 1) if ',' in dados_assinatura else (None, dados_assinatura)
                with open(filepath, 'wb') as f: f.write(base64.b64decode(encoded))

            elif tipo_assinatura == 'upload':
                if not dados_assinatura: return False, "Arquivo vazio."
                dados_assinatura.save(filepath)

            siblings = db.session.scalars(
                select(DiarioClasse).where(
                    DiarioClasse.data_aula == diario_pai.data_aula,
                    DiarioClasse.turma_id == diario_pai.turma_id,
                    DiarioClasse.disciplina_id == diario_pai.disciplina_id,
                    DiarioClasse.status == 'pendente'
                )
            ).all()

            count = 0
            timestamp = datetime.now()
            for d in siblings:
                d.assinatura_path = db_path
                d.status = 'assinado'
                d.data_assinatura = timestamp
                d.instrutor_assinante_id = user_id
                count += 1

            if salvar_padrao and tipo_assinatura in ['canvas', 'upload']:
                def_name = f"default_{instrutor.id}.png"
                def_path = os.path.join(upload_folder, def_name)
                shutil.copy2(filepath, def_path)
                instrutor.assinatura_padrao_path = f"uploads/signatures/{def_name}"

            db.session.commit()
            return True, f"Sucesso! {count} aulas validadas em bloco."

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro assinatura: {e}")
            return False, f"Erro: {str(e)}"