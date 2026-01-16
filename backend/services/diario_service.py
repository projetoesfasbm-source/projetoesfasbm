# backend/services/diario_service.py
import os
import base64
import uuid
import shutil
from datetime import datetime
from flask import current_app
from ..models.database import db
from ..models.diario_classe import DiarioClasse
from ..models.horario import Horario
from ..models.instrutor import Instrutor
from ..models.turma import Turma
from ..models.semana import Semana
from sqlalchemy import select, and_

class DiarioService:
    
    @staticmethod
    def get_diarios_pendentes_instrutor(user_id):
        instrutor = db.session.scalars(select(Instrutor).where(Instrutor.user_id == user_id)).first()
        if not instrutor:
            return []

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
                Horario.instrutor_id == instrutor.id,
                DiarioClasse.status == 'pendente',
                DiarioClasse.conteudo_ministrado != None,
                DiarioClasse.conteudo_ministrado != '',
                Semana.data_inicio <= DiarioClasse.data_aula,
                Semana.data_fim >= DiarioClasse.data_aula
            )
            .order_by(DiarioClasse.data_aula.desc())
        )
        return db.session.scalars(stmt.distinct()).all()

    @staticmethod
    def get_diario_para_assinatura(diario_id, user_id):
        instrutor = db.session.scalars(select(Instrutor).where(Instrutor.user_id == user_id)).first()
        if not instrutor:
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
                Horario.instrutor_id == instrutor.id,
                Semana.data_inicio <= DiarioClasse.data_aula,
                Semana.data_fim >= DiarioClasse.data_aula
            )
        )
        # Retorna tupla (Diario, Instrutor) para facilitar acesso no controller
        return db.session.scalars(stmt).first(), instrutor

    @staticmethod
    def assinar_diario(diario_id, user_id, tipo_assinatura, dados_assinatura=None, salvar_padrao=False):
        """
        Processa a assinatura.
        tipo_assinatura: 'padrao', 'canvas' ou 'upload'
        salvar_padrao: Booleano, se deve atualizar o perfil do instrutor
        """
        diario, instrutor = DiarioService.get_diario_para_assinatura(diario_id, user_id)
        if not diario:
            return False, "Permissão negada ou diário não encontrado."

        # Configura pastas
        base_path = os.path.join(current_app.root_path, '..', 'static')
        upload_folder = os.path.join(base_path, 'uploads', 'signatures')
        os.makedirs(upload_folder, exist_ok=True)
        
        # Nome único para ESTE documento (Auditoria: nunca sobrescreva assinaturas de documentos passados)
        filename = f"sig_diario_{diario.id}_{uuid.uuid4().hex[:8]}.png"
        filepath = os.path.join(upload_folder, filename)
        db_path = f"uploads/signatures/{filename}"

        try:
            # CASO 1: Usar Assinatura Padrão
            if tipo_assinatura == 'padrao':
                if not instrutor.assinatura_padrao_path:
                    return False, "Você não possui uma assinatura padrão salva."
                
                # Copia o arquivo padrão para o arquivo deste diário específico
                source_path = os.path.join(base_path, instrutor.assinatura_padrao_path)
                if not os.path.exists(source_path):
                    return False, "Arquivo de assinatura padrão não encontrado no servidor."
                
                shutil.copy2(source_path, filepath)

            # CASO 2: Assinatura Desenhada (Canvas)
            elif tipo_assinatura == 'canvas':
                if not dados_assinatura: return False, "Assinatura vazia."
                
                if ',' in dados_assinatura:
                    header, encoded = dados_assinatura.split(',', 1)
                else:
                    encoded = dados_assinatura
                
                img_data = base64.b64decode(encoded)
                with open(filepath, 'wb') as f:
                    f.write(img_data)

            # CASO 3: Upload de Arquivo
            elif tipo_assinatura == 'upload':
                if not dados_assinatura: return False, "Arquivo não fornecido."
                dados_assinatura.save(filepath)

            else:
                return False, "Método inválido."

            # Atualiza Diário
            diario.assinatura_path = db_path
            diario.status = 'assinado'
            diario.data_assinatura = datetime.now()
            diario.instrutor_assinante_id = user_id

            # Lógica para SALVAR COMO PADRÃO (se solicitado)
            if salvar_padrao and tipo_assinatura in ['canvas', 'upload']:
                # Cria um arquivo específico para ser o "default"
                default_filename = f"default_sig_instrutor_{instrutor.id}.png"
                default_filepath = os.path.join(upload_folder, default_filename)
                
                # Copia do arquivo recém gerado para o default
                shutil.copy2(filepath, default_filepath)
                
                # Atualiza perfil do instrutor
                instrutor.assinatura_padrao_path = f"uploads/signatures/{default_filename}"

            db.session.commit()
            return True, "Diário assinado com sucesso."

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao assinar: {e}")
            return False, f"Erro técnico: {str(e)}"