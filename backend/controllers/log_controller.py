from flask import Blueprint, request, render_template
from flask_login import login_required, current_user
from backend.services.log_service import LogService
from backend.models.user import User
from backend.models.database import db
from datetime import datetime
import math # <-- NOVO IMPORT PARA O CÁLCULO DE PÁGINAS

# --- CLASSE AUXILIAR DE PAGINAÇÃO ---
# Essa classe envelopa a lista que vem do LogService para que o HTML consiga
# usar os comandos .items, .pages, .iter_pages() sem quebrar o código existente.
class ListPagination:
    def __init__(self, items, page, per_page, total):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        self.pages = int(math.ceil(total / float(per_page))) if per_page else 0
        self.has_prev = page > 1
        self.has_next = page < self.pages
        self.prev_num = page - 1 if self.has_prev else None
        self.next_num = page + 1 if self.has_next else None

    def iter_pages(self, left_edge=1, left_current=2, right_current=2, right_edge=1):
        last = 0
        for num in range(1, self.pages + 1):
            if num <= left_edge or \
               (num > self.page - left_current - 1 and num < self.page + right_current) or \
               num > self.pages - right_edge:
                if last + 1 != num:
                    yield None
                yield num
                last = num
# ------------------------------------

log_bp = Blueprint('log_controller', __name__)

@log_bp.route('/logs', methods=['GET'])
@login_required
def render_logs_page():
    """Rota para buscar os logs e renderizar a página HTML"""
    
    # 1. Segurança: Apenas admins e super_admins
    if current_user.role not in ['super_admin', 'admin']: 
         return "Acesso Negado", 403

    # 2. Pega os filtros crus da URL e a página atual
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    filtro_user_id = request.args.get('user_id')
    page = request.args.get('page', 1, type=int) # <-- Captura a página (padrão: 1)
    per_page = 15 # <-- Define a quantidade de logs por página

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
    # Aumentamos o limite para 5000 para que a paginação possa cobrir um longo histórico.
    logs_db_list = LogService.get_logs(
        school_id=school_id, 
        date_start=date_start_obj, 
        date_end=date_end_obj,     
        user_id=filtro_user_id,
        limit=5000 
    )

    # --- INÍCIO DA LÓGICA DE PAGINAÇÃO ---
    total_logs = len(logs_db_list)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    # Fatiamos a lista para pegar apenas os 15 itens da página atual
    paginated_items = logs_db_list[start_idx:end_idx]
    
    # Criamos o objeto envelopado que o HTML vai conseguir ler (logs.items, logs.pages)
    logs_paginados = ListPagination(paginated_items, page, per_page, total_logs)
    # --- FIM DA LÓGICA DE PAGINAÇÃO ---

    # 5. Busca todos os usuários DAQUELA ESCOLA para preencher o filtro
    users = db.session.query(User).filter(
        User.user_schools.any(school_id=school_id)
    ).all()

    # 6. Entrega tudo para o HTML desenhar a tela
    return render_template(
        'ferramentas/logs_admin.html', 
        logs=logs_paginados, # <-- Passando o objeto paginado
        users=users,
        data_inicio=data_inicio or '',
        data_fim=data_fim or '',
        filtro_user_id=filtro_user_id
    )
