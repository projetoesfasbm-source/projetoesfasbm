# backend/controllers/questionario_controller.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from sqlalchemy import select, func, distinct

from ..models.database import db
from ..models.questionario import Questionario
from ..models.pergunta import Pergunta
from ..models.opcao_resposta import OpcaoResposta
from ..models.resposta import Resposta
from ..models.user import User

questionario_bp = Blueprint('questionario', __name__, url_prefix='/questionario')

@questionario_bp.route('/')
@login_required
def index():
    return render_template('questionario/index.html')

@questionario_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo_questionario():
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        if not titulo:
            flash('O título do questionário é obrigatório.', 'danger')
            return render_template('questionario/novo.html')

        novo_questionario = Questionario(titulo=titulo)
        db.session.add(novo_questionario)
        db.session.flush()

        perguntas_data = {}
        for key, value in request.form.items():
            if key.startswith('pergunta_'):
                index = key.split('_')[1]
                if index not in perguntas_data:
                    perguntas_data[index] = {'opcoes': []}
                perguntas_data[index]['texto'] = value
            elif key.startswith('tipo_'):
                index = key.split('_')[1]
                if index not in perguntas_data:
                    perguntas_data[index] = {'opcoes': []}
                perguntas_data[index]['tipo'] = value
            elif key.startswith('opcao_'):
                parts = key.split('_')
                p_index, o_index = parts[1], parts[2]
                if p_index not in perguntas_data:
                    perguntas_data[p_index] = {'opcoes': []}
                perguntas_data[p_index]['opcoes'].append(value)
            elif key.startswith('outro_'):
                index = key.split('_')[1]
                if index not in perguntas_data:
                    perguntas_data[index] = {'opcoes': []}
                perguntas_data[index]['outro'] = True

        for index, data in perguntas_data.items():
            if data.get('texto'):
                pergunta = Pergunta(
                    texto=data['texto'],
                    questionario_id=novo_questionario.id,
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
                        opcao_outro = OpcaoResposta(texto='Outro', pergunta_id=pergunta.id)
                        db.session.add(opcao_outro)

        db.session.commit()
        flash('Questionário criado com sucesso!', 'success')
        return redirect(url_for('questionario.index'))
        
    return render_template('questionario/novo.html')

@questionario_bp.route('/ver')
@login_required
def ver_questionarios():
    questionarios = db.session.scalars(select(Questionario).order_by(Questionario.titulo)).all()
    return render_template('questionario/ver.html', questionarios=questionarios)

@questionario_bp.route('/resultado/<int:questionario_id>')
@login_required
def resultado_questionario(questionario_id):
    questionario = db.session.get(Questionario, questionario_id)
    if not questionario:
        flash('Questionário não encontrado.', 'danger')
        return redirect(url_for('questionario.ver_questionarios'))
        
    dados_graficos = {}
    respostas_texto = {}
    for pergunta in questionario.perguntas:
        if pergunta.tipo == 'texto_livre':
            respostas = db.session.scalars(select(Resposta).where(Resposta.pergunta_id == pergunta.id, Resposta.texto_livre.isnot(None))).all()
            if respostas:
                respostas_texto[pergunta.id] = {'texto': pergunta.texto, 'respostas': [r.texto_livre for r in respostas]}
        else:
            labels = [opcao.texto for opcao in pergunta.opcoes]
            dados = []
            for opcao in pergunta.opcoes:
                count = db.session.query(func.count(Resposta.id)).filter_by(pergunta_id=pergunta.id, opcao_resposta_id=opcao.id).scalar()
                dados.append(count)
            dados_graficos[pergunta.id] = {'labels': labels, 'dados': dados}

    return render_template(
        'questionario/resultado.html', 
        questionario=questionario, 
        dados_graficos=dados_graficos,
        respostas_texto=respostas_texto
    )

@questionario_bp.route('/realizar', methods=['GET', 'POST'])
@login_required
def realizar_questionario():
    if request.method == 'POST':
        questionario_id = request.form.get('questionario_id')
        user_id = request.form.get('user_id')

        if not questionario_id or not user_id:
            flash('Por favor, selecione um questionário e um usuário.', 'danger')
            return redirect(url_for('questionario.realizar_questionario'))

        questionario = db.session.get(Questionario, int(questionario_id))
        
        for pergunta in questionario.perguntas:
            if pergunta.tipo == 'texto_livre':
                texto_livre = request.form.get(f'texto_livre_{pergunta.id}')
                if texto_livre:
                    nova_resposta = Resposta(
                        questionario_id=questionario.id, pergunta_id=pergunta.id,
                        user_id=int(user_id), texto_livre=texto_livre
                    )
                    db.session.add(nova_resposta)
            else:
                respostas_ids = request.form.getlist(f'pergunta_{pergunta.id}')
                for resposta_id in respostas_ids:
                    opcao_selecionada = db.session.get(OpcaoResposta, int(resposta_id))
                    texto_livre_outro = None
                    if opcao_selecionada and opcao_selecionada.texto in ['Outro', 'Outra área', 'Outro motivo', 'Outra forma', 'Quais']:
                        texto_livre_outro = request.form.get(f'outro_{pergunta.id}')

                    nova_resposta = Resposta(
                        questionario_id=questionario.id, pergunta_id=pergunta.id,
                        user_id=int(user_id), opcao_resposta_id=int(resposta_id),
                        texto_livre=texto_livre_outro
                    )
                    db.session.add(nova_resposta)
        
        db.session.commit()
        flash('Questionário respondido com sucesso!', 'success')
        return redirect(url_for('questionario.index'))

    questionarios = db.session.scalars(select(Questionario).order_by(Questionario.titulo)).all()
    
    alunos_objs = db.session.scalars(select(User).where(User.role == 'aluno').order_by(User.nome_completo)).all()
    instrutores_objs = db.session.scalars(select(User).where(User.role == 'instrutor').order_by(User.nome_completo)).all()

    # --- ALTERAÇÃO APLICADA AQUI: Adiciona a matrícula aos dados ---
    alunos_data = [{'id': u.id, 'nome_completo': u.nome_completo or u.username, 'matricula': u.matricula} for u in alunos_objs]
    instrutores_data = [{'id': u.id, 'nome_completo': u.nome_completo or u.username, 'matricula': u.matricula} for u in instrutores_objs]

    return render_template('questionario/realizar.html', 
                           questionarios=questionarios, 
                           alunos=alunos_data, 
                           instrutores=instrutores_data)

@questionario_bp.route('/api/get-perguntas/<int:questionario_id>')
@login_required
def get_perguntas(questionario_id):
    questionario = db.session.get(Questionario, questionario_id)
    if not questionario:
        return jsonify({'error': 'Questionário não encontrado'}), 404
        
    perguntas_list = []
    for p in questionario.perguntas:
        opcoes_list = [{'id': o.id, 'texto': o.texto} for o in p.opcoes]
        perguntas_list.append({'id': p.id, 'texto': p.texto, 'tipo': p.tipo, 'opcoes': opcoes_list})
        
    return jsonify(perguntas_list)

@questionario_bp.route('/excluir/<int:questionario_id>', methods=['POST'])
@login_required
def excluir_questionario(questionario_id):
    questionario = db.session.get(Questionario, questionario_id)
    if not questionario:
        flash('Questionário não encontrado.', 'danger')
        return redirect(url_for('questionario.ver_questionarios'))

    try:
        db.session.query(Resposta).filter_by(questionario_id=questionario_id).delete()
        db.session.delete(questionario)
        db.session.commit()
        flash('Questionário e todas as suas respostas foram excluídos com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir o questionário: {e}', 'danger')
        
    return redirect(url_for('questionario.ver_questionarios'))

@questionario_bp.route('/participantes/<int:questionario_id>')
@login_required
def ver_participantes(questionario_id):
    questionario = db.session.get(Questionario, questionario_id)
    if not questionario:
        flash('Questionário não encontrado.', 'danger')
        return redirect(url_for('questionario.ver_questionarios'))
    
    user_ids = db.session.scalars(
        select(distinct(Resposta.user_id)).where(Resposta.questionario_id == questionario_id)
    ).all()
    
    participantes = []
    if user_ids:
        participantes = db.session.scalars(
            select(User).where(User.id.in_(user_ids)).order_by(User.nome_completo)
        ).all()
        
    return render_template('questionario/participantes.html', questionario=questionario, participantes=participantes)

@questionario_bp.route('/editar-respostas/<int:questionario_id>/<int:user_id>', methods=['GET', 'POST'])
@login_required
def editar_respostas(questionario_id, user_id):
    pass

@questionario_bp.route('/excluir-resposta/<int:questionario_id>/<int:user_id>', methods=['POST'])
@login_required
def excluir_resposta_usuario(questionario_id, user_id):
    pass