# backend/controllers/cursos_controller.py
import os
import json
from flask import Blueprint, send_from_directory, request, jsonify, session, redirect, render_template_string
from backend.models.database import db
from backend.models.curso_video import CursoVideo
from backend.extensions import csrf

# Mantém a API original do SQL caso seja utilizada externamente
cursos_api_bp = Blueprint('cursos_api', __name__, url_prefix='/api/cursos')

@cursos_api_bp.route('/videos', methods=['GET'])
def get_videos():
    videos = CursoVideo.query.order_by(CursoVideo.created_at.desc()).all()
    return jsonify([v.to_dict() for v in videos]), 200

@cursos_api_bp.route('/videos', methods=['POST'])
def add_video():
    data = request.json
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

@cursos_api_bp.route('/videos/<int:video_id>', methods=['DELETE'])
def delete_video(video_id):
    video = CursoVideo.query.get(video_id)
    if not video:
        return jsonify({'error': 'Vídeo não encontrado'}), 404
    db.session.delete(video)
    db.session.commit()
    return jsonify({'message': 'Vídeo removido com sucesso'}), 200


# Novo Blueprint para servir a pasta /cursos/ e emular o PHP
cursos_bp = Blueprint('cursos_bp', __name__)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CURSOS_DIR = os.path.join(PROJECT_ROOT, 'cursos')

DEFAULT_DATA = {
    'videos': [
        {
            'id': 'v1',
            'name': 'Manual de Sobrevivência do Aluno - Primeiros Passos',
            'category': 'Alunos',
            'url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
            'thumbnail': 'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=500&auto=format&fit=crop'
        },
        {
            'id': 'v2',
            'name': 'Guia de Acesso e Direitos de Trânsito Interno',
            'category': 'Alunos',
            'url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4',
            'thumbnail': 'https://images.unsplash.com/photo-1506784983877-45594efa4cbe?w=500&auto=format&fit=crop'
        },
        {
            'id': 'v3',
            'name': 'Diretrizes Acadêmicas e Metodologia de Instrução',
            'category': 'Instrutores',
            'url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4',
            'thumbnail': 'https://images.unsplash.com/photo-1524178232363-1fb2b075b655?w=500&auto=format&fit=crop'
        },
        {
            'id': 'v4',
            'name': 'Tutorial: Lançamento de Diários de Classe e Presenças',
            'category': 'Instrutores',
            'url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4',
            'thumbnail': 'https://images.unsplash.com/photo-1434030216411-0b793f4b4173?w=500&auto=format&fit=crop'
        },
        {
            'id': 'v5',
            'name': 'Painel Administrativo: Auditoria de Logs do Sistema',
            'category': 'Adm',
            'url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4',
            'thumbnail': 'https://images.unsplash.com/photo-1551836022-d5d88e9218df?w=500&auto=format&fit=crop'
        },
        {
            'id': 'v6',
            'name': 'Procedimento Operacional: Backup e Migração de Dados',
            'category': 'Adm',
            'url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/SubaruOutback.mp4',
            'thumbnail': 'https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?w=500&auto=format&fit=crop'
        }
    ],
    'logo': {
        'type': 'text',
        'text': 'SisG<span>En</span> CURSOS',
        'imageUrl': '',
        'bannerBgType': 'url',
        'bannerBgUrl': ''
    },
    'intro': {
        'logoText': 'SisG<span>En</span>',
        'subtext': 'PLATAFORMA DE CURSOS',
        'duration': 3
    }
}

def get_cursos_data():
    data_file = os.path.join(PROJECT_ROOT, 'static', 'uploads', 'cursos_data.json')
    if not os.path.exists(data_file):
        os.makedirs(os.path.dirname(data_file), exist_ok=True)
        # Tenta ler do diretório cursos caso tenha sido comitado lá primeiro
        fallback_file = os.path.join(CURSOS_DIR, 'cursos_data.json')
        if os.path.exists(fallback_file):
            try:
                import shutil
                shutil.copy(fallback_file, data_file)
            except Exception:
                pass
        if not os.path.exists(data_file):
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_DATA, f, indent=4, ensure_ascii=False)
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return DEFAULT_DATA

def save_cursos_data(data):
    data_file = os.path.join(PROJECT_ROOT, 'static', 'uploads', 'cursos_data.json')
    os.makedirs(os.path.dirname(data_file), exist_ok=True)
    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

@cursos_bp.route('/cursos/api.php', methods=['GET', 'POST'])
@csrf.exempt
def api_php():
    current_data = get_cursos_data()
    if request.method == 'GET':
        return jsonify(current_data)
    
    # POST
    if not session.get('cursos_authenticated'):
        return jsonify({'error': 'Não autenticado no painel de cursos.'}), 403
        
    input_data = request.get_json(silent=True)
    if input_data is None:
        return jsonify({'error': 'JSON Inválido'}), 400
        
    action = input_data.get('action')
    if action:
        if action == 'save_videos':
            current_data['videos'] = input_data.get('videos', [])
        elif action == 'save_logo':
            current_data['logo'] = input_data.get('logo', {})
        elif action == 'save_intro':
            current_data['intro'] = input_data.get('intro', {})
        elif action == 'restore_defaults':
            current_data = DEFAULT_DATA
        else:
            return jsonify({'error': 'Nenhuma ação válida especificada.'}), 400
            
        save_cursos_data(current_data)
        return jsonify({'success': True})
        
    return jsonify({'error': 'Nenhuma ação válida especificada.'}), 400

@cursos_bp.route('/cursos/admin_painel.php', methods=['GET', 'POST'])
@csrf.exempt
def admin_painel_php():
    config_password = 'Sisgen@2026'
    error = ''
    
    if request.args.get('logout') == '1':
        session.pop('cursos_authenticated', None)
        return redirect('/cursos/admin_painel.php')
        
    if request.method == 'POST' and request.form.get('action') == 'login':
        password = request.form.get('password')
        if password == config_password:
            session['cursos_authenticated'] = True
            return redirect('/cursos/admin_painel.php')
        else:
            error = 'Senha incorreta!'
            
    authenticated = session.get('cursos_authenticated', False)
    
    admin_file = os.path.join(CURSOS_DIR, 'admin_painel.php')
    if not os.path.exists(admin_file):
        return "admin_painel.php não encontrado", 404
        
    with open(admin_file, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Remove o cabeçalho PHP inicial do arquivo
    idx = content.find('?>')
    if idx != -1:
        html_part = content[idx+2:].strip()
    else:
        html_part = content
        
    # Substitui construções condicionais do PHP por Jinja2
    html_part = html_part.replace('<?php if (!$authenticated): ?>', '{% if not authenticated %}')
    html_part = html_part.replace('<?php if ($error): ?>', '{% if error %}')
    html_part = html_part.replace('<?= htmlspecialchars($error) ?>', '{{ error }}')
    html_part = html_part.replace('<?php else: ?>', '{% else %}')
    html_part = html_part.replace('<?php endif; ?>', '{% endif %}')
    
    return render_template_string(html_part, authenticated=authenticated, error=error)

@cursos_bp.route('/cursos/')
@cursos_bp.route('/cursos/<path:filename>')
def serve_cursos_static(filename='index.html'):
    if filename == 'api.php':
        return api_php()
    if filename == 'admin_painel.php':
        return admin_painel_php()
    if filename == 'cursos_data.json':
        uploads_dir = os.path.join(PROJECT_ROOT, 'static', 'uploads')
        return send_from_directory(uploads_dir, 'cursos_data.json')
    return send_from_directory(CURSOS_DIR, filename)
