from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy import select, func, distinct

from ..models.database import db
from ..models.questionario import Questionario
from ..models.pergunta import Pergunta
from ..models.opcao_resposta import OpcaoResposta
from ..models.resposta import Resposta
from ..models.user import User

questionario_bp = Blueprint('questionario', __name__, url_prefix='/questionario')

# Helper para permissões
def cal_or_admin_required():
    if not (current_user.is_cal or current_user.is_admin_escola or current_user.is_programador or current_user.is_super_admin):
        flash('Acesso não autorizado.', 'danger')
        return False
    return True

@questionario_bp.route('/')
@login_required
def index():
    questionarios = db.session.scalars(select(Questionario).order_by(Questionario.id.desc())).all()
    return render_template('questionario/index.html', questionarios=questionarios)

@questionario_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo():
    if not cal_or_admin_required():
        return redirect(url_for('questionario.index'))

    if request.method == 'POST':
        titulo = request.form.get('titulo')
        publico_alvo = request.form.get('publico_alvo', 'todos')
        
        if not titulo:
            flash('O título do questionário é obrigatório.', 'danger')
            return render_template('questionario/novo.html')

        novo_q = Questionario(titulo=titulo, publico_alvo=publico_alvo, ativo=True)
        db.session.add(novo_q)
        db.session.flush()

        perguntas_data = {}
        for key, value in request.form.items():
            if key.startswith('pergunta_'):
                index = key.split('_')[1]
                if index not in perguntas_data: perguntas_data[index] = {'opcoes': []}
                perguntas_data[index]['texto'] = value
            elif key.startswith('tipo_'):
                index = key.split('_')[1]
                if index not in perguntas_data: perguntas_data[index] = {'opcoes': []}
                perguntas_data[index]['tipo'] = value
            elif key.startswith('opcao_'):
                parts = key.split('_')
                if len(parts) >= 3:
                    p_index = parts[1]
                    if p_index not in perguntas_data: perguntas_data[p_index] = {'opcoes': []}
                    perguntas_data[p_index]['opcoes'].append(value)
            elif key.startswith('outro_'):
                index = key.split('_')[1]
                if index not in perguntas_data: perguntas_data[index] = {'opcoes': []}
                perguntas_data[index]['outro'] = True

        for index, data in perguntas_data.items():
            if data.get('texto'):
                pergunta = Pergunta(
                    texto=data['texto'],
                    questionario_id=novo_q.id,
                    tipo=data.get('tipo', 'unica')
                )
                db.session.add(pergunta)
                db.session.flush()

                if data.get('tipo') != 'texto_livre':
                    for opt_texto in data['opcoes']:
                        if opt_texto:
                            opcao = OpcaoResposta(texto=opt_texto, pergunta_id=pergunta.id)
                            db.session.add(opcao)
                    if data.get('outro'):
                        db.session.add(OpcaoResposta(texto='Outro', pergunta_id=pergunta.id))

        db.session.commit()
        flash('Questionário criado com sucesso!', 'success')
        return redirect(url_for('questionario.index'))
        
    return render_template('questionario/novo.html')

@questionario_bp.route('/ver/<int:id>')
@login_required
def ver(id):
    # Visualização para Admin/CAL (Preview)
    if not cal_or_admin_required():
        return redirect(url_for('questionario.index'))
        
    questionario = db.session.get(Questionario, id)
    if not questionario:
        flash('Questionário não encontrado.', 'danger')
        return redirect(url_for('questionario.index'))
    return render_template('questionario/realizar.html', questionario=questionario, preview=True)

@questionario_bp.route('/resultado/<int:id>')
@login_required
def resultado(id):
    # Permitir SENS ver resultados também? Se sim, adicione is_sens
    if not (current_user.is_cal or current_user.is_sens or current_user.is_staff):
        flash('Permissão negada.', 'danger')
        return redirect(url_for('questionario.index'))

    questionario = db.session.get(Questionario, id)
    if not questionario:
        flash('Questionário não encontrado.', 'danger')
        return redirect(url_for('questionario.index'))
        
    dados_graficos = {}
    respostas_texto = {}
    
    # Lógica simplificada de contagem
    for pergunta in questionario.perguntas:
        if pergunta.tipo == 'texto_livre':
            respostas = db.session.scalars(select(Resposta).where(Resposta.pergunta_id == pergunta.id, Resposta.texto_livre.isnot(None))).all()
            if respostas:
                respostas_texto[pergunta.id] = {'texto': pergunta.texto, 'respostas': [r.texto_livre for r in respostas]}
        else:
            labels = [opcao.texto for opcao in pergunta.opcoes]
            dados = []
            for opcao in pergunta.opcoes:
                count = db.session.query(func.count(Resposta.id)).filter_by(opcao_resposta_id=opcao.id).scalar()
                dados.append(count or 0)
            dados_graficos[pergunta.id] = {'labels': labels, 'dados': dados, 'texto': pergunta.texto}

    return render_template(
        'questionario/resultado.html', 
        questionario=questionario, 
        dados_graficos=dados_graficos,
        respostas_texto=respostas_texto
    )

@questionario_bp.route('/realizar/<int:id>', methods=['GET', 'POST'])
@login_required
def realizar(id):
    questionario = db.session.get(Questionario, id)
    if not questionario or not questionario.ativo:
        flash('Questionário indisponível.', 'warning')
        return redirect(url_for('questionario.index'))

    # Verifica se usuário já respondeu
    ja_respondeu = db.session.scalar(select(Resposta).where(Resposta.questionario_id == id, Resposta.user_id == current_user.id))
    if ja_respondeu:
        flash('Você já respondeu este questionário.', 'info')
        return redirect(url_for('questionario.index'))

    if request.method == 'POST':
        for pergunta in questionario.perguntas:
            if pergunta.tipo == 'texto_livre':
                texto = request.form.get(f'texto_livre_{pergunta.id}')
                if texto:
                    db.session.add(Resposta(questionario_id=id, pergunta_id=pergunta.id, user_id=current_user.id, texto_livre=texto))
            else:
                opcoes_ids = request.form.getlist(f'pergunta_{pergunta.id}')
                texto_outro = request.form.get(f'outro_{pergunta.id}')
                
                for op_id in opcoes_ids:
                    db.session.add(Resposta(questionario_id=id, pergunta_id=pergunta.id, opcao_resposta_id=int(op_id), user_id=current_user.id, texto_livre=texto_outro))
        
        db.session.commit()
        flash('Respostas enviadas com sucesso!', 'success')
        return redirect(url_for('questionario.index'))

    return render_template('questionario/realizar.html', questionario=questionario)

@questionario_bp.route('/participantes/<int:questionario_id>')
@login_required
def participantes(questionario_id):
    if not cal_or_admin_required():
        return redirect(url_for('questionario.index'))

    questionario = db.session.get(Questionario, questionario_id)
    user_ids = db.session.scalars(select(distinct(Resposta.user_id)).where(Resposta.questionario_id == questionario_id)).all()
    users = db.session.scalars(select(User).where(User.id.in_(user_ids))).all() if user_ids else []
    
    return render_template('questionario/participantes.html', questionario=questionario, participantes=users)

@questionario_bp.route('/alternar-status/<int:id>')
@login_required
def alternar_status(id):
    if not cal_or_admin_required(): return redirect(url_for('questionario.index'))
    
    q = db.session.get(Questionario, id)
    if q:
        q.ativo = not q.ativo
        db.session.commit()
        flash(f'Questionário {"ativado" if q.ativo else "desativado"}.', 'success')
    return redirect(url_for('questionario.index'))

@questionario_bp.route('/excluir/<int:id>')
@login_required
def excluir(id):
    if not cal_or_admin_required(): return redirect(url_for('questionario.index'))
    
    q = db.session.get(Questionario, id)
    if q:
        db.session.query(Resposta).filter_by(questionario_id=id).delete()
        db.session.delete(q)
        db.session.commit()
        flash('Questionário excluído.', 'success')
    return redirect(url_for('questionario.index'))