# backend/controllers/cursos_controller.py
from flask import Blueprint, jsonify, request
from backend.models.database import db
from backend.models.curso_video import CursoVideo
# from flask_login import login_required, current_user # (Usaremos depois para proteger)

cursos_api_bp = Blueprint('cursos_api', __name__, url_prefix='/api/cursos')

# --- Rota para LISTAR todos os vídeos (Para a página inicial e Painel) ---
@cursos_api_bp.route('/videos', methods=['GET'])
def get_videos():
    videos = CursoVideo.query.order_by(CursoVideo.created_at.desc()).all()
    return jsonify([v.to_dict() for v in videos]), 200

# --- Rota para ADICIONAR um vídeo (Para o Painel de Controle) ---
@cursos_api_bp.route('/videos', methods=['POST'])
def add_video():
    data = request.json
    
    # Validação básica
    if not data or not data.get('name') or not data.get('url') or not data.get('category'):
        return jsonify({'error': 'Dados incompletos'}), 400

    novo_video = CursoVideo(
        name=data.get('name'),
        category=data.get('category'),
        url=data.get('url'),
        thumbnail=data.get('thumbnail')
    )
    
    db.session.add(novo_video)
    db.session.commit()
    
    return jsonify(novo_video.to_dict()), 201

# --- Rota para DELETAR um vídeo (Para o Painel de Controle) ---
@cursos_api_bp.route('/videos/<int:video_id>', methods=['DELETE'])
def delete_video(video_id):
    video = CursoVideo.query.get(video_id)
    if not video:
        return jsonify({'error': 'Vídeo não encontrado'}), 404
        
    db.session.delete(video)
    db.session.commit()
    
    return jsonify({'message': 'Vídeo removido com sucesso'}), 200
