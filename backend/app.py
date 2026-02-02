# backend/app.py

import os
import click
import firebase_admin
from flask import Flask, render_template, g, session, send_from_directory
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_babel import Babel
from firebase_admin import credentials

from backend.config import Config
from backend.extensions import limiter
from backend.models.database import db
from backend.models.user import User
from backend.services.asset_service import AssetService

# --- Importações de TODOS os modelos para o Flask-Migrate ---
from backend.models.aluno import Aluno
from backend.models.avaliacao import AvaliacaoAtitudinal, AvaliacaoItem
from backend.models.disciplina import Disciplina
from backend.models.disciplina_turma import DisciplinaTurma
from backend.models.discipline_rule import DisciplineRule
from backend.models.historico import HistoricoAluno
from backend.models.historico_disciplina import HistoricoDisciplina
from backend.models.horario import Horario
from backend.models.image_asset import ImageAsset
from backend.models.instrutor import Instrutor
from backend.models.notification import Notification
from backend.models.opcao_resposta import OpcaoResposta
from backend.models.password_reset_token import PasswordResetToken
from backend.models.pergunta import Pergunta
from backend.models.processo_disciplina import ProcessoDisciplina
from backend.models.push_subscription import PushSubscription
from backend.models.questionario import Questionario
from backend.models.resposta import Resposta
from backend.models.school import School
from backend.models.semana import Semana
from backend.models.site_config import SiteConfig
from backend.models.turma import Turma
from backend.models.turma_cargo import TurmaCargo
from backend.models.user_school import UserSchool
from backend.models.fada_avaliacao import FadaAvaliacao
from backend.models.diario_classe import DiarioClasse
from backend.models.frequencia import FrequenciaAluno
# ### NOVO MODELO ###
from backend.models.elogio import Elogio
# ------------------------------------------------------------
from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

def create_app(config_class=Config):
    """
    Fábrica de aplicação: cria e configura a instância do Flask.
    """
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    template_dir = os.path.join(project_root, 'templates')
    static_dir = os.path.join(project_root, 'static')

    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    app.config.from_object(config_class)

    config_class.init_app(app)

    # --- INICIALIZAÇÃO DO FIREBASE ---
    try:
        cred_path = os.path.join(os.path.dirname(__file__), 'credentials.json')
        if os.path.exists(cred_path):
            if not firebase_admin._apps:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                app.logger.info("Firebase Admin SDK inicializado com sucesso.")
        else:
                 app.logger.warning(f"Arquivo 'credentials.json' não encontrado em {cred_path}. Funcionalidades do Firebase não estarão disponíveis.")
    except ValueError:
       pass # App já inicializado
    except Exception as e:
        app.logger.error(f"ERRO ao inicializar o Firebase Admin SDK: {e}")
    # --- FIM DA INICIALIZAÇÃO ---

    # ### FILTRO DE FUSO HORÁRIO ###
    @app.template_filter('br_time')
    def format_datetime_as_brt(dt_utc, format_str=None):
        if not dt_utc:
            return "N/A"
        try:
            BRT = ZoneInfo("America/Sao_Paulo")
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=timezone.utc)
            dt_brt = dt_utc.astimezone(BRT)
            if format_str:
                return dt_brt.strftime(format_str)
            else:
                return dt_brt.strftime("%d/%m/%Y às %H:%M")
        except Exception as e:
            return str(dt_utc)
    # ### FIM DO FILTRO ###

    # ### PWA ###
    @app.route('/sw.js')
    def service_worker():
        return send_from_directory(app.static_folder, 'sw.js', mimetype='application/javascript')

    @app.route('/manifest.json')
    def manifest():
        return send_from_directory(app.static_folder, 'manifest.json', mimetype='application/json')
    # ### FIM PWA ###

    db.init_app(app)
    Migrate(app, db)
    CSRFProtect(app)
    limiter.init_app(app)
    Babel(app)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # =========================================================
    # CORREÇÃO CRÍTICA DE PERMISSÕES POR ESCOLA (Context Inject)
    # =========================================================
    @app.before_request
    def set_user_context():
        if current_user.is_authenticated:
            if current_user.role in ['super_admin', 'programador']:
                view_as = session.get('view_as_school_id')
                if view_as:
                    current_user.temp_active_school_id = int(view_as)
                    return

            sid = session.get('active_school_id')
            if sid:
                current_user.temp_active_school_id = int(sid)
    # =========================================================

    with app.app_context():
        AssetService.initialize_upload_folder(app)
        register_blueprints(app)
        register_handlers_and_processors(app)

    register_cli_commands(app)
    return app

def register_blueprints(app):
    """Importa e registra os blueprints na aplicação."""
    from backend.controllers.admin_controller import admin_escola_bp
    from backend.controllers.admin_tools_controller import tools_bp
    from backend.controllers.aluno_controller import aluno_bp
    from backend.controllers.assets_controller import assets_bp
    from backend.controllers.auth_controller import auth_bp
    from backend.controllers.avaliacao_controller import avaliacao_bp
    from backend.controllers.customizer_controller import customizer_bp
    from backend.controllers.disciplina_controller import disciplina_bp
    from backend.controllers.historico_controller import historico_bp
    from backend.controllers.horario_controller import horario_bp
    from backend.controllers.instrutor_controller import instrutor_bp
    from backend.controllers.justica_controller import justica_bp
    from backend.controllers.main_controller import main_bp
    from backend.controllers.notification_controller import notification_bp
    from backend.controllers.push_controller import push_bp
    from backend.controllers.questionario_controller import questionario_bp
    from backend.controllers.relatorios_controller import relatorios_bp
    from backend.controllers.semana_controller import semana_bp
    from backend.controllers.super_admin_controller import super_admin_bp
    from backend.controllers.turma_controller import turma_bp
    from backend.controllers.user_controller import user_bp
    from backend.controllers.vinculo_controller import vinculo_bp
    from backend.controllers.chefe_turma_controller import chefe_bp

    # ### NOVOS CONTROLLERS ###
    from backend.controllers.elogio_controller import elogio_bp
    from backend.controllers.regras_controller import regras_bp
    from backend.controllers.diario_controller import diario_bp

    app.register_blueprint(admin_escola_bp)
    app.register_blueprint(tools_bp)
    app.register_blueprint(aluno_bp)
    app.register_blueprint(assets_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(avaliacao_bp)
    app.register_blueprint(customizer_bp)
    app.register_blueprint(disciplina_bp)
    app.register_blueprint(historico_bp)
    app.register_blueprint(horario_bp)
    app.register_blueprint(instrutor_bp)
    app.register_blueprint(justica_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(push_bp)
    app.register_blueprint(questionario_bp)
    app.register_blueprint(relatorios_bp)
    app.register_blueprint(semana_bp)
    app.register_blueprint(super_admin_bp)
    app.register_blueprint(turma_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(vinculo_bp)
    app.register_blueprint(chefe_bp)

    # ### REGISTRO DE NOVOS BLUEPRINTS ###
    app.register_blueprint(elogio_bp)
    app.register_blueprint(regras_bp)
    app.register_blueprint(diario_bp)

def register_handlers_and_processors(app):

    @app.before_request
    def load_globals():
        from backend.services.site_config_service import SiteConfigService

        if 'site_config' not in g:
            if app.config.get("TESTING", False):
                SiteConfigService.init_default_configs()

            configs = SiteConfigService.get_all_configs()
            g.site_config = {c.config_key: c.config_value for c in configs}

        g.active_school = None
        school_id_to_load = None

        if current_user.is_authenticated:
            if current_user.role in ['super_admin', 'programador']:
                school_id_to_load = session.get('view_as_school_id')

            if school_id_to_load is None:
                 school_id_to_load = session.get('active_school_id')

            if school_id_to_load is None and hasattr(current_user, 'user_schools') and current_user.user_schools:
                school_id_to_load = current_user.user_schools[0].school_id

            if school_id_to_load:
                g.active_school = db.session.get(School, int(school_id_to_load))


    @app.context_processor
    def inject_globals_to_template():
        return {
            'site_config': g.get('site_config'),
            'active_school': g.get('active_school')
        }

    @app.after_request
    def add_header(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        csp = [
            "default-src 'self'",
            "script-src 'self' https://code.jquery.com https://cdn.jsdelivr.net 'unsafe-eval' 'unsafe-inline'",
            "style-src 'self' https://cdn.jsdelivr.net https://fonts.googleapis.com 'unsafe-inline'",
            "font-src 'self' https://fonts.gstatic.com",
            "img-src 'self' data: *",
            "connect-src 'self' https://cdn.jsdelivr.net",
            "object-src 'none'",
            "frame-ancestors 'self'",
            "manifest-src 'self'",
            "worker-src 'self'"
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp)

        return response

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('500.html'), 500

def register_cli_commands(app):
    @app.cli.command("create-super-admin")
    def create_super_admin():
        with app.app_context():
            super_admin_password = os.environ.get('SUPER_ADMIN_PASSWORD')
            if not super_admin_password:
                print("A variável de ambiente SUPER_ADMIN_PASSWORD não está definida.")
                return
            user = db.session.execute(db.select(User).filter_by(username='super_admin')).scalar_one_or_none()
            if user:
                print("Usuário 'super_admin' já existe. Atualizando senha e ativando...")
                user.is_active = True
                user.set_password(super_admin_password)
            else:
                print("Criando o usuário super administrador 'super_admin'...")
                user = User(
                    matricula='SUPER_ADMIN',
                    username='super_admin',
                    email='super_admin@escola.com.br',
                    role='super_admin',
                    is_active=True
                )
                user.set_password(super_admin_password)
                db.session.add(user)
            db.session.commit()
            print("Comando executado com sucesso!")

    @app.cli.command("create-programmer")
    def create_programmer():
        with app.app_context():
            prog_password = os.environ.get('PROGRAMMER_PASSWORD')
            if not prog_password:
                print("A variável de ambiente PROGRAMMER_PASSWORD não está definida.")
                return
            user = db.session.execute(db.select(User).filter_by(matricula='PROG001')).scalar_one_or_none()
            if user:
                print("O usuário 'programador' já existe.")
            else:
                print("Criando o usuário programador...")
                user = User(
                    matricula='PROG001',
                    username='programador',
                    email='dev@escola.com.br',
                    role='programador',
                    is_active=True
                )
                user.set_password(prog_password)
                db.session.add(user)
            db.session.commit()
            print("Usuário programador criado com sucesso!")

    @app.cli.command("clear-data")
    @click.option('--app', is_flag=True, help='Limpa apenas os dados da aplicação (alunos, turmas, etc).')
    def clear_data_command(app_flag):
        from scripts.clear_data import clear_transactional_data
        if not app_flag:
                if input("ATENÇÃO: Este comando irá apagar TODOS os dados de alunos, turmas, etc. Deseja continuar? (s/n): ").lower() != 's':
                    print("Operação cancelada.")
                    return
        with create_app().app_context():
            clear_transactional_data()

    @app.cli.command("seed-questionario")
    def seed_questionario_command():
        from scripts.seed_questionario import popular_questionario_db
        with create_app().app_context():
            popular_questionario_db()
        print("Comando de popular questionário executado.")

    @app.cli.command("seed-npccal")
    def seed_npccal_command():
        """Popula o banco de dados com as regras de disciplina (NPCCAL)."""
        from scripts.seed_npccal import seed_rules
        with app.app_context():
            seed_rules()

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)