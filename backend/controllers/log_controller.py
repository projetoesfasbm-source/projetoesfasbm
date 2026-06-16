from flask import Blueprint, request, render_template
from flask_login import login_required, current_user
from backend.services.log_service import LogService
from backend.models.user import User
from backend.models.database import db
from datetime import datetime # <-- IMPORTAÇÃO NECESSÁRIA AQUI

log_bp = Blueprint('log_controller', __name__)

@log_bp.route('/logs', methods=['GET'])
@login_required
def render_logs_page():
    """Rota para buscar os logs e renderizar a página HTML"""
    
    # 1. Segurança: Apenas admins e super_admins
    if current_user.role not in ['super_admin', 'admin']: 
         return "Acesso Negado", 403

    # 2. Pega os filtros crus da URL
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    filtro_user_id = request.args.get('user_id')

    # --- INÍCIO DA CORREÇÃO DE DATAS ---
    date_start_obj = None
    date_end_obj = None

    if data_inicio:
        try:
            # Converte a string 'YYYY-MM-DD' para data
            date_start_obj = datetime.strptime(data_inicio, '%Y-%m-%d')
        except ValueError:
            pass

    if data_fim:
        try:
            # Converte a string e força o horário para o último segundo do dia
            date_end_obj = datetime.strptime(data_fim, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        except ValueError:
            pass
    # --- FIM DA CORREÇÃO DE DATAS ---

    # Ajusta o ID do usuário para número, se houver
    if filtro_user_id and filtro_user_id.isdigit():
        filtro_user_id = int(filtro_user_id)
    else:
        filtro_user_id = None

    # 3. Busca a escola ativa no momento
    school_id = current_user.temp_active_school_id or current_user.school_id

    # 4. Busca os logs no banco de dados usando os objetos de data corrigidos
    logs_db = LogService.get_logs(
        school_id=school_id, 
        date_start=date_start_obj, # <-- Passando o objeto de data
        date_end=date_end_obj,     # <-- Passando o objeto de data (23:59:59)
        user_id=filtro_user_id,
        limit=200
    )

    # 5. Busca todos os usuários DAQUELA ESCOLA para preencher o filtro
    users = db.session.query(User).filter(
        User.user_schools.any(school_id=school_id)
    ).all()

    # 6. Entrega tudo para o HTML desenhar a tela
    return render_template(
        'ferramentas/logs_admin.html', 
        logs=logs_db,
        users=users,
        data_inicio=data_inicio or '',
        data_fim=data_fim or '',
        filtro_user_id=filtro_user_id
    )
