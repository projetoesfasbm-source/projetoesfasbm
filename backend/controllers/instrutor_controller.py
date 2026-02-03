# backend/controllers/instrutor_controller.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from wtforms import StringField, SelectField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Optional, Email, EqualTo
from flask_wtf import FlaskForm
from datetime import datetime, timedelta, timezone, date
from sqlalchemy.orm import joinedload
from copy import copy  # <--- IMPORTANTE: Usado para corrigir a data visualmente

from ..services.instrutor_service import InstrutorService
from ..services.user_service import UserService
from ..models.instrutor import Instrutor
from ..models.horario import Horario
from ..models.database import db

from utils.decorators import (
    admin_or_programmer_required,
    school_admin_or_programmer_required,
    can_view_management_pages_required
)

instrutor_bp = Blueprint("instrutor", __name__, url_prefix="/instrutor")

posto_graduacao_structured = {
    'Praças': ['Soldado PM', '2º Sargento PM', '1º Sargento PM'],
    'Oficiais': ['1º Tenente PM', 'Capitão PM', 'Major PM', 'Tenente-Coronel PM', 'Coronel PM'],
    'Saúde - Enfermagem': ['Ten Enf', 'Cap Enf', 'Maj Enf', 'Ten Cel Enf', 'Cel Enf'],
    'Saúde - Médicos': ['Ten Med', 'Cap Med', 'Maj Med', 'Ten Cel Med', 'Cel Med'],
    'Outros': ['Civil', 'Outro']
}

class InstrutorForm(FlaskForm):
    nome_completo = StringField("Nome Completo", validators=[DataRequired()])
    nome_de_guerra = StringField("Nome de Guerra", validators=[DataRequired()])
    matricula = StringField("Matrícula", validators=[DataRequired()])
    email = StringField("E-mail", validators=[DataRequired(), Email()])
    password = PasswordField("Senha", validators=[DataRequired(), EqualTo("password2", message="As senhas devem corresponder.")])
    password2 = PasswordField("Confirmar Senha", validators=[DataRequired()])
    
    posto_categoria = SelectField("Categoria", choices=list(posto_graduacao_structured.keys()), validators=[DataRequired()])
    posto_graduacao = SelectField("Posto/Graduação", validators=[DataRequired()])
    posto_graduacao_outro = StringField("Outro (especifique)", validators=[Optional()])

    telefone = StringField("Telefone", validators=[Optional()])
    is_rr = SelectField("Efetivo da Reserva Remunerada (RR)", choices=[('0', 'Não'), ('1', 'Sim')], default='0')
    submit = SubmitField("Salvar")


class EditInstrutorForm(FlaskForm):
    nome_completo = StringField("Nome Completo", validators=[DataRequired()])
    nome_de_guerra = StringField("Nome de Guerra", validators=[DataRequired()])
    matricula = StringField("Matrícula", render_kw={"readonly": True})
    email = StringField("E-mail", validators=[DataRequired(), Email()])
    
    posto_categoria = SelectField("Categoria", choices=list(posto_graduacao_structured.keys()), validators=[DataRequired()])
    posto_graduacao = SelectField("Posto/Graduação", validators=[DataRequired()])
    posto_graduacao_outro = StringField("Outro (especifique)", validators=[Optional()])

    telefone = StringField("Telefone", validators=[Optional()])
    is_rr = SelectField("Efetivo da Reserva Remunerada (RR)", choices=[('0', 'Não'), ('1', 'Sim')], default='0')
    submit = SubmitField("Salvar Alterações")


class DeleteForm(FlaskForm):
    pass


@instrutor_bp.route("/")
@login_required
@can_view_management_pages_required
def listar_instrutores():
    page = request.args.get('page', 1, type=int)
    search_term = request.args.get('q', None)
    
    instrutores_paginados = InstrutorService.get_all_instrutores(current_user, search_term=search_term, page=page, per_page=15)
    delete_form = DeleteForm()

    return render_template(
        "listar_instrutores.html", 
        instrutores_paginados=instrutores_paginados, 
        delete_form=delete_form,
        search_term=search_term
    )


@instrutor_bp.route("/cadastrar", methods=["GET", "POST"])
@login_required
@school_admin_or_programmer_required
def cadastrar_instrutor():
    form = InstrutorForm()
    
    if form.is_submitted():
         categoria_selecionada = form.posto_categoria.data
         if categoria_selecionada in posto_graduacao_structured:
              form.posto_graduacao.choices = [(p, p) for p in posto_graduacao_structured[categoria_selecionada]]

    if form.validate_on_submit():
        school_id = UserService.get_current_school_id()
        if not school_id:
            flash("Não foi possível identificar a escola para associar o instrutor.", "danger")
            return redirect(url_for("instrutor.listar_instrutores"))

        form_data = form.data.copy()
        form_data['is_rr'] = True if form.is_rr.data == '1' else False

        success, message = InstrutorService.create_full_instrutor(form_data, school_id)
        if success:
            flash(message, "success")
            return redirect(url_for("instrutor.listar_instrutores"))
        else:
            flash(message, "danger")

    return render_template("cadastro_instrutor.html", form=form, postos_data=posto_graduacao_structured)


@instrutor_bp.route("/editar/<int:instrutor_id>", methods=["GET", "POST"])
@login_required
@school_admin_or_programmer_required
def editar_instrutor(instrutor_id):
    instrutor = InstrutorService.get_instrutor_by_id(instrutor_id)
    if not instrutor or not instrutor.user:
        flash("Instrutor não encontrado.", "danger")
        return redirect(url_for("instrutor.listar_instrutores"))

    form = EditInstrutorForm(obj=instrutor)
    
    if request.method == 'GET':
        form.nome_completo.data = instrutor.user.nome_completo
        form.nome_de_guerra.data = instrutor.user.nome_de_guerra
        form.matricula.data = instrutor.user.matricula
        form.email.data = instrutor.user.email
        form.is_rr.data = '1' if instrutor.is_rr else '0'

        posto_atual = instrutor.user.posto_graduacao
        categoria_encontrada = None
        for categoria, postos in posto_graduacao_structured.items():
            if posto_atual in postos:
                categoria_encontrada = categoria
                break
        
        if categoria_encontrada:
            form.posto_categoria.data = categoria_encontrada
            form.posto_graduacao.choices = [(p, p) for p in posto_graduacao_structured[categoria_encontrada]]
            form.posto_graduacao.data = posto_atual
        elif posto_atual:
            form.posto_categoria.data = 'Outros'
            form.posto_graduacao.choices = [(p, p) for p in posto_graduacao_structured['Outros']]
            form.posto_graduacao.data = 'Outro'
            form.posto_graduacao_outro.data = posto_atual
    
    if form.is_submitted():
         categoria_selecionada = form.posto_categoria.data
         if categoria_selecionada in posto_graduacao_structured:
              form.posto_graduacao.choices = [(p, p) for p in posto_graduacao_structured[categoria_selecionada]]

    if form.validate_on_submit():
        try:
            instrutor.user.nome_completo = form.nome_completo.data
            instrutor.user.nome_de_guerra = form.nome_de_guerra.data
            instrutor.user.email = form.email.data
            
            if form.posto_graduacao.data == 'Outro':
                instrutor.user.posto_graduacao = form.posto_graduacao_outro.data
            else:
                instrutor.user.posto_graduacao = form.posto_graduacao.data

            instrutor.telefone = form.telefone.data
            instrutor.is_rr = (form.is_rr.data == '1')

            db.session.commit()
            flash("Instrutor atualizado com sucesso.", "success")
            return redirect(url_for("instrutor.listar_instrutores"))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao atualizar: {str(e)}", "danger")

    return render_template("editar_instrutor.html", form=form, instrutor=instrutor, postos_data=posto_graduacao_structured)


@instrutor_bp.route('/dashboard/content')
@login_required
def dashboard_content():
    # --- Verificação de Permissão ---
    is_authorized = False
    
    if hasattr(current_user, 'has_role') and current_user.has_role('instrutor'):
        is_authorized = True
    elif hasattr(current_user, 'role') and str(current_user.role) == 'instrutor':
        is_authorized = True
    
    if not is_authorized:
        user_role = str(getattr(current_user, 'role', ''))
        if getattr(current_user, 'is_admin', False) or user_role in ['admin', 'programmer', 'school_admin']:
            is_authorized = True

    if not is_authorized:
        flash("Acesso restrito a instrutores.", "danger")
        return redirect(url_for('main.index'))

    try:
        instrutor = Instrutor.query.filter_by(user_id=current_user.id).first()
        
        # --- DEFINIÇÃO DO MOMENTO ATUAL ---
        agora_brasil = datetime.now(timezone.utc) - timedelta(hours=3)
        agora_comparacao = agora_brasil.replace(tzinfo=None)
        hoje = agora_brasil.date()

        if not instrutor:
            return render_template('horario/dashboard_instrutor_content.html', 
                                   error="Instrutor não encontrado.",
                                   aulas_futuras=[], aulas_passadas=[],
                                   total_futuros=0, total_ministrados=0,
                                   stats_disciplinas={}, hoje=hoje)

        # Busca todas as aulas carregando a semana e a disciplina
        aulas = Horario.query.filter_by(instrutor_id=instrutor.id)\
            .options(joinedload(Horario.turma), joinedload(Horario.disciplina), joinedload(Horario.semana))\
            .all()

        aulas_futuras = []
        aulas_passadas = []
        stats_disciplinas = {}

        # --- FUNÇÃO AUXILIAR DE CÁLCULO ---
        def calcular_data_real(semana_inicio, nome_dia):
            if not semana_inicio or not nome_dia: return semana_inicio
            d_lower = nome_dia.lower()
            offset = 0
            if 'seg' in d_lower or '2' in d_lower: offset = 0
            elif 'ter' in d_lower or '3' in d_lower: offset = 1
            elif 'qua' in d_lower or '4' in d_lower: offset = 2
            elif 'qui' in d_lower or '5' in d_lower: offset = 3
            elif 'sex' in d_lower or '6' in d_lower: offset = 4
            elif 'sab' in d_lower or 'sáb' in d_lower: offset = 5
            elif 'dom' in d_lower: offset = 6
            return semana_inicio + timedelta(days=offset)

        for aula in aulas:
            if aula.disciplina:
                nome_disc = aula.disciplina.nome
                stats_disciplinas[nome_disc] = stats_disciplinas.get(nome_disc, 0) + 1

            # --- CORREÇÃO VISUAL DA DATA (SUBSTITUIÇÃO DE OBJETO) ---
            # 1. Calculamos a data correta baseada no dia da semana escrito
            data_correta = None
            if aula.semana and aula.semana.data_inicio and aula.dia_semana:
                data_correta = calcular_data_real(aula.semana.data_inicio, aula.dia_semana)

            # 2. Se conseguimos calcular, injetamos essa data no objeto
            if data_correta:
                # Criamos um atributo direto 'data_aula' caso o template use ele
                aula.data_aula = data_correta
                
                # TRUQUE PARA O HTML:
                # Se o HTML usa 'aula.semana.data_inicio', precisamos substituir a semana
                # por uma cópia que tenha a data_inicio alterada APENAS para esta aula.
                # Isso não afeta o banco de dados.
                semana_fake = copy(aula.semana)
                semana_fake.data_inicio = data_correta
                aula.semana = semana_fake

            # --- Separação Futuro vs Passado ---
            # Usa a data_correta calculada acima
            data_para_comparar = data_correta if data_correta else getattr(aula, 'data_aula', date.min)
            
            try:
                eh_futuro = False
                if data_para_comparar and aula.hora_inicio:
                    dt_aula = datetime.combine(data_para_comparar, aula.hora_inicio)
                    if dt_aula > agora_comparacao:
                        eh_futuro = True
                elif data_para_comparar and data_para_comparar > hoje:
                    eh_futuro = True
                
                if eh_futuro:
                    aulas_futuras.append(aula)
                else:
                    aulas_passadas.append(aula)
            except Exception:
                aulas_passadas.append(aula)

        # Ordenação
        aulas_futuras.sort(key=lambda x: (getattr(x, 'data_aula', date.max), getattr(x, 'hora_inicio', datetime.min.time())))

        return render_template('horario/dashboard_instrutor_content.html',
                               instrutor=instrutor,
                               aulas_futuras=aulas_futuras,
                               aulas_passadas=aulas_passadas,
                               total_futuros=len(aulas_futuras),
                               total_ministrados=len(aulas_passadas),
                               stats_disciplinas=stats_disciplinas,
                               hoje=hoje)

    except Exception as e:
        current_app.logger.error(f"Erro no dashboard: {str(e)}")
        return render_template('horario/dashboard_instrutor_content.html', 
                               error="Erro ao carregar dados.",
                               aulas_futuras=[], aulas_passadas=[],
                               hoje=datetime.now().date())