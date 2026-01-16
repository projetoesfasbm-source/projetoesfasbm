# backend/services/diario_service.py
import os
import base64
import uuid
from datetime import datetime
from flask import current_app
from ..models.database import db
from ..models.diario_classe import DiarioClasse
from ..models.horario import Horario
from ..models.instrutor import Instrutor
from sqlalchemy import select, and_

class DiarioService:
    
    @staticmethod
    def get_diarios_pendentes_instrutor(user_id):
        """
        Busca diários preenchidos (que possuem conteúdo) mas ainda não assinados,
        vinculados ao instrutor logado via Horario.
        """
        # 1. Encontrar o ID de Instrutor do Usuário
        instrutor = db.session.scalars(select(Instrutor).where(Instrutor.user_id == user_id)).first()
        if not instrutor:
            return []

        # 2. Buscar Diários Pendentes ligados aos horários deste instrutor
        # Filtra apenas diários que têm conteúdo (foram preenchidos) mas status é pendente
        stmt = (
            select(DiarioClasse)
            .join(Horario)
            .where(
                Horario.instrutor_id == instrutor.id,
                DiarioClasse.status == 'pendente',
                DiarioClasse.conteudo_ministrado != None,
                DiarioClasse.conteudo_ministrado != ''
            )
            .order_by(DiarioClasse.data_aula.desc())
        )
        return db.session.scalars(stmt).all()

    @staticmethod
    def get_diario_para_assinatura(diario_id, user_id):
        """
        Busca um diário específico validando se pertence ao instrutor.
        """
        instrutor = db.session.scalars(select(Instrutor).where(Instrutor.user_id == user_id)).first()
        if not instrutor:
            return None

        stmt = (
            select(DiarioClasse)
            .join(Horario)
            .where(
                DiarioClasse.id == diario_id,
                Horario.instrutor_id == instrutor.id
            )
        )
        return db.session.scalars(stmt).first()

    @staticmethod
    def assinar_diario(diario_id, user_id, tipo_assinatura, dados_assinatura):
        """
        Processa a assinatura (Canvas ou Upload), salva o arquivo e atualiza o banco.
        tipo_assinatura: 'canvas' ou 'upload'
        dados_assinatura: string base64 (canvas) ou objeto FileStorage (upload)
        """
        diario = DiarioService.get_diario_para_assinatura(diario_id, user_id)
        if not diario:
            return False, "Diário não encontrado ou permissão negada."

        # Diretório de salvamento
        upload_folder = os.path.join(current_app.root_path, '..', 'static', 'uploads', 'signatures')
        os.makedirs(upload_folder, exist_ok=True)
        
        filename = f"sig_{diario.id}_{uuid.uuid4().hex[:8]}.png"
        filepath = os.path.join(upload_folder, filename)
        db_path = f"uploads/signatures/{filename}"

        try:
            if tipo_assinatura == 'canvas':
                # Remove o cabeçalho 'data:image/png;base64,' se existir
                if ',' in dados_assinatura:
                    header, encoded = dados_assinatura.split(',', 1)
                else:
                    encoded = dados_assinatura
                
                img_data = base64.b64decode(encoded)
                with open(filepath, 'wb') as f:
                    f.write(img_data)
            
            elif tipo_assinatura == 'upload':
                dados_assinatura.save(filepath)
            
            else:
                return False, "Tipo de assinatura inválido."

            # Atualizar Registro no Banco
            diario.assinatura_path = db_path
            diario.status = 'assinado'
            diario.data_assinatura = datetime.now()
            diario.instrutor_assinante_id = user_id
            
            db.session.commit()
            return True, "Diário assinado e validado com sucesso."

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao salvar assinatura: {e}")
            return False, f"Erro interno ao processar assinatura: {str(e)}"