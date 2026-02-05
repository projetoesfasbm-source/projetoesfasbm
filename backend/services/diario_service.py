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
from ..models.disciplina_turma import DisciplinaTurma
from ..models.frequencia import FrequenciaAluno
from ..models.aluno import Aluno
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
                subquery_vinculos = select(DisciplinaTurma.disciplina_id).where(
                    or_(
                        DisciplinaTurma.instrutor_id_1 == instrutor.id,
                        DisciplinaTurma.instrutor_id_2 == instrutor.id
                    )
                )
                stmt = stmt.where(DiarioClasse.disciplina_id.in_(subquery_vinculos))
            else:
                return []

        if turma_id: stmt = stmt.where(DiarioClasse.turma_id == turma_id)
        if disciplina_id: stmt = stmt.where(DiarioClasse.disciplina_id == disciplina_id)

        stmt = stmt.order_by(DiarioClasse.data_aula.desc(), DiarioClasse.periodo)
        return db.session.scalars(stmt.distinct()).all()

    @staticmethod
    def get_diarios_agrupados(school_id, user_id=None, turma_id=None, disciplina_id=None, status=None):
        raw_diarios = DiarioService.get_diarios_pendentes(school_id, user_id, turma_id, disciplina_id, status)
        
        if not raw_diarios: return []

        grouped_diarios = []
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
        rep = group_items[0] 
        first_p = group_items[0].periodo
        last_p = group_items[-1].periodo
        
        if first_p is None: rep.periodo_resumo = "N/D"
        elif first_p == last_p: rep.periodo_resumo = f"{first_p}º Período"
        else: rep.periodo_resumo = f"{first_p}º a {last_p}º Período"
            
        rep.total_aulas_bloco = len(group_items)
        return rep

    @staticmethod
    def get_filtros_disponiveis(school_id, user_id=None, turma_selected_id=None):
        instrutor = DiarioService.get_current_instrutor(user_id) if user_id else None
        
        stmt_turmas = select(Turma).where(Turma.school_id == school_id).order_by(Turma.nome)
        turmas = db.session.scalars(stmt_turmas).all()

        stmt_disc = select(Disciplina).join(Turma).where(Turma.school_id == school_id)
        if turma_selected_id:
            stmt_disc = stmt_disc.where(Disciplina.turma_id == turma_selected_id)
            
        if instrutor:
            vinculos = select(DisciplinaTurma.disciplina_id).where(
                or_(DisciplinaTurma.instrutor_id_1 == instrutor.id, 
                    DisciplinaTurma.instrutor_id_2 == instrutor.id)
            )
            stmt_disc = stmt_disc.where(Disciplina.id.in_(vinculos))

        disciplinas = db.session.scalars(stmt_disc.distinct()).all()
        unique_disciplinas = sorted({d.materia: d for d in disciplinas}.values(), key=lambda x: x.materia)

        return turmas, unique_disciplinas

    @staticmethod
    def get_diario_para_assinatura(diario_id, user_id):
        instrutor = DiarioService.get_current_instrutor(user_id)
        if not instrutor: return None, None
        
        diario = db.session.get(DiarioClasse, diario_id)
        if not diario: return None, None

        vinculo = db.session.scalars(
            select(DisciplinaTurma).where(
                DisciplinaTurma.disciplina_id == diario.disciplina_id,
                or_(DisciplinaTurma.instrutor_id_1 == instrutor.id, 
                    DisciplinaTurma.instrutor_id_2 == instrutor.id)
            )
        ).first()

        if vinculo:
            return diario, instrutor
            
        return None, None

    @staticmethod
    def assinar_diario(diario_id, user_id, tipo_assinatura, dados_assinatura=None, salvar_padrao=False, conteudo_atualizado=None, observacoes_atualizadas=None):
        diario_pai, instrutor = DiarioService.get_diario_para_assinatura(diario_id, user_id)
        if not diario_pai:
            return False, "Permissão negada."

        base_path = os.path.join(current_app.root_path, '..', 'static')
        upload_folder = os.path.join(base_path, 'uploads', 'signatures')
        os.makedirs(upload_folder, exist_ok=True)
        
        filename = f"sig_diario_{diario_pai.id}_{uuid.uuid4().hex[:8]}.png"
        filepath = os.path.join(upload_folder, filename)
        db_path = f"uploads/signatures/{filename}"

        try:
            if tipo_assinatura == 'padrao':
                if not instrutor.assinatura_padrao_path: return False, "Sem assinatura padrão."
                shutil.copy2(os.path.join(base_path, instrutor.assinatura_padrao_path), filepath)
            elif tipo_assinatura == 'canvas':
                header, encoded = dados_assinatura.split(',', 1) if ',' in dados_assinatura else (None, dados_assinatura)
                with open(filepath, 'wb') as f: f.write(base64.b64decode(encoded))
            elif tipo_assinatura == 'upload':
                dados_assinatura.save(filepath)

            siblings = db.session.scalars(
                select(DiarioClasse).where(
                    DiarioClasse.data_aula == diario_pai.data_aula,
                    DiarioClasse.turma_id == diario_pai.turma_id,
                    DiarioClasse.disciplina_id == diario_pai.disciplina_id,
                    DiarioClasse.status == 'pendente'
                )
            ).all()

            timestamp = datetime.now()
            for d in siblings:
                d.assinatura_path = db_path
                d.status = 'assinado'
                d.data_assinatura = timestamp
                d.instrutor_assinante_id = user_id
                if conteudo_atualizado: d.conteudo_ministrado = conteudo_atualizado
                if observacoes_atualizadas is not None: d.observacoes = observacoes_atualizadas

            db.session.commit()
            return True, f"Sucesso! {len(siblings)} aulas assinadas."
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def retornar_diario_admin(diario_id, admin_user, motivo_devolucao):
        diario = db.session.get(DiarioClasse, diario_id)
        if not diario: return False, "Não encontrado."
        try:
            siblings = db.session.scalars(select(DiarioClasse).where(
                DiarioClasse.data_aula == diario.data_aula,
                DiarioClasse.turma_id == diario.turma_id,
                DiarioClasse.disciplina_id == diario.disciplina_id
            )).all()
            for d in siblings:
                d.status = 'pendente'
                d.assinatura_path = None
                d.data_assinatura = None
                d.observacoes = (d.observacoes or "") + f"\n[DEVOLVIDO]: {motivo_devolucao}"
            db.session.commit()
            return True, "Aulas devolvidas."
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def atualizar_conteudo_admin(diario_id, novo_conteudo, novas_obs):
        diario = db.session.get(DiarioClasse, diario_id)
        if not diario: return False, "Não encontrado."
        try:
            siblings = db.session.scalars(select(DiarioClasse).where(
                DiarioClasse.data_aula == diario.data_aula,
                DiarioClasse.turma_id == diario.turma_id,
                DiarioClasse.disciplina_id == diario.disciplina_id
            )).all()
            for d in siblings:
                d.conteudo_ministrado = novo_conteudo
                d.observacoes = novas_obs
            db.session.commit()
            return True, "Atualizado."
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def get_faltas_report_data(school_id, data_inicio, data_fim, turma_id=None):
        """
        Busca consolidada de faltas.
        Retorna uma lista de dicionários para evitar erros de mapeamento de tupla no template.
        """
        stmt = (
            select(FrequenciaAluno, Aluno, DiarioClasse, Turma, Disciplina)
            .join(Aluno, FrequenciaAluno.aluno_id == Aluno.id)
            .join(DiarioClasse, FrequenciaAluno.diario_id == DiarioClasse.id)
            .join(Turma, DiarioClasse.turma_id == Turma.id)
            .join(Disciplina, DiarioClasse.disciplina_id == Disciplina.id)
            .where(
                Turma.school_id == school_id,
                FrequenciaAluno.presente == False,
                DiarioClasse.data_aula >= data_inicio,
                DiarioClasse.data_aula <= data_fim
            )
        )

        if turma_id:
            stmt = stmt.where(Turma.id == turma_id)

        stmt = stmt.order_by(DiarioClasse.data_aula.asc(), Aluno.nome.asc())
        results = db.session.execute(stmt).all()
        
        # Converte para formato amigável ao template
        report = []
        for row in results:
            report.append({
                'data': row.DiarioClasse.data_aula,
                'matricula': row.Aluno.idfunc,
                'aluno_nome': row.Aluno.nome,
                'turma_nome': row.Turma.nome,
                'disciplina_nome': row.Disciplina.nome
            })
        return report