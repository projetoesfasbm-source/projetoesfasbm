import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from ..models.database import db
from ..models.chamado_suporte import ChamadoSuporte
from utils.image_utils import allowed_file, generate_unique_filename

suporte_bp = Blueprint('suporte', __name__, url_prefix='/suporte')

@suporte_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo_chamado():
    if request.method == 'POST':
        qso_contato = request.form.get('qso_contato')
        tipo_login = request.form.get('tipo_login')
        matricula_problema = request.form.get('matricula_problema')
        tipo_problema = request.form.get('tipo_problema')
        descricao = request.form.get('descricao')
        
        if not qso_contato or not tipo_login or not tipo_problema or not descricao:
            flash('Por favor, preencha todos os campos obrigatórios.', 'error')
            return redirect(request.url)

        # Tratar anexo opcional
        file = request.files.get('anexo')
        unique_filename = None
        
        if file and file.filename != '':
            ALLOWED_ASSET_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'doc', 'docx'}
            if allowed_file(file.filename, file.stream, ALLOWED_ASSET_EXTENSIONS):
                upload_folder = os.path.join(current_app.root_path, '..', 'static', 'uploads')
                os.makedirs(upload_folder, exist_ok=True)
                
                original_filename = secure_filename(file.filename)
                unique_filename = generate_unique_filename(original_filename)
                file_path = os.path.join(upload_folder, unique_filename)
                
                file.stream.seek(0)
                file.save(file_path)
            else:
                flash('Tipo de arquivo não permitido.', 'error')
                return redirect(request.url)

        # Buscar escola ativa do usuário se houver
        escola_id = None
        if hasattr(current_user, '_get_active_school_id'):
            escola_id = current_user._get_active_school_id()
            
        chamado = ChamadoSuporte(
            solicitante_id=current_user.id,
            escola_id=escola_id,
            qso_contato=qso_contato,
            tipo_login=tipo_login,
            matricula_problema=matricula_problema,
            tipo_problema=tipo_problema,
            descricao=descricao,
            anexo_filename=unique_filename
        )
        
        try:
            db.session.add(chamado)
            db.session.commit()
            flash('Seu chamado foi registrado com sucesso. A equipe de suporte já foi notificada!', 'success')
            return redirect(url_for('suporte.novo_chamado'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Erro ao criar chamado: {e}')
            flash('Ocorreu um erro ao registrar o chamado. Tente novamente mais tarde.', 'error')
            
    # Para o GET, pegar a escola atual para preencher no form
    escola_nome = ""
    if hasattr(current_user, '_get_active_school_id'):
        escola_id = current_user._get_active_school_id()
        if escola_id:
            from ..models.school import School
            escola = db.session.get(School, escola_id)
            if escola:
                escola_nome = escola.nome
                
    return render_template('suporte/novo.html', escola_nome=escola_nome)

@suporte_bp.route('/admin')
@login_required
def admin_chamados():
    if not (current_user.is_staff or current_user.is_super_admin):
        flash('Você não tem permissão para acessar esta página.', 'error')
        return redirect(url_for('main.index'))
        
    chamados = db.session.query(ChamadoSuporte).order_by(
        ChamadoSuporte.status.asc(), # 'Aberto' vem antes de 'Concluido'
        ChamadoSuporte.data_criacao.desc()
    ).all()
    
    return render_template('suporte/admin.html', chamados=chamados)

@suporte_bp.route('/admin/<int:chamado_id>/concluir', methods=['POST'])
@login_required
def concluir_chamado(chamado_id):
    if not (current_user.is_staff or current_user.is_super_admin):
        return jsonify({'success': False, 'message': 'Sem permissão.'}), 403
        
    chamado = db.session.get(ChamadoSuporte, chamado_id)
    if not chamado:
        return jsonify({'success': False, 'message': 'Chamado não encontrado.'}), 404
        
    if chamado.status != 'Concluido':
        chamado.status = 'Concluido'
        chamado.data_conclusao = datetime.utcnow()
        try:
            db.session.commit()
            return jsonify({'success': True, 'message': 'Chamado marcado como concluído!'})
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Erro ao concluir chamado: {e}')
            return jsonify({'success': False, 'message': 'Erro interno ao salvar no banco.'}), 500
            
    return jsonify({'success': True, 'message': 'Chamado já estava concluído.'})
