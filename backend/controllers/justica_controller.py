# backend/controllers/justica_controller.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, Response
from flask_login import login_required, current_user
from sqlalchemy import select, or_
import locale

from ..models.database import db
from ..models.aluno import Aluno
from ..models.user import User
from ..services.justica_service import JusticaService
from utils.decorators import admin_or_programmer_required

justica_bp = Blueprint('justica', __name__, url_prefix='/justica-e-disciplina')

# Lista de infrações extraída da normativa
FATOS_PREDEFINIDOS = [
    "I - Movimentar-se em forma, sem prévia autorização;",
    "II - Afastar-se do quartel sem tomar conhecimento do aditamento, ordens e recomendações do dia;",
    "III - Demonstrar sonolência, desatenção ou displicência em atividade do CAI ou instrução;",
    "IV - Não primar pela manutenção e limpeza das áreas de uso comum;",
    "V - Deixar de comunicar ao Comandante do Pelotão mudança de endereço e telefones;",
    "VI - Não manter limpo e devidamente organizado os locais de uso individual ou coletivo;",
    "VII - Não primar pelo bom estado de conservação e limpeza de material carga;",
    "VIII - Deixar material abandonado ou em local que não deva permanecer;",
    "XIV - Portar-se em local público sem observar a postura e os preceitos éticos;",
    "XV - Dirigir-se a repartição ou a local restrito sem estar autorizado;",
    "XVI - Estar desatento na leitura do aditamento interno ou na transmissão de ordens;",
    "XVII - Apresentar-se com fardamento incompleto, desalinhado, mal passado ou não regulamentar;",
    "XVIII - Portar objeto, mesmo de uso particular, que contraste com o uniforme;",
    "XIX - Deixar de observar normas internas para o estacionamento de viaturas;",
    "XX - Deixar de portar a Carteira de Identidade Militar e o cartão do IPERGS;",
    "XXI - Apresentar-se com o cabelo, barba, unhas em desacordo com o estabelecido;",
    "XXII - Aproveitar-se de formaturas ou serviço para ocultar suas faltas ou irregularidades;",
    "XXVI - Deixar de observar rigorosamente os preceitos de regulamentos ou normas;",
    "XXVII - Deixar, quando na função de comando ou em serviço, de cumprir as prescrições afetas as suas funções;",
    "XXVIII - Dirigir-se à autoridade superior sem percorrer o canal hierárquico;",
    "XXIX - Extraviar, danificar ou deixar de encaminhar documentos específicos ao ensino;",
    "XXX - Entrar ou sair do local sem a devida permissão de superior hierárquico;",
    "XXXI - Manter em sua posse qualquer material ou objeto sem autorização;",
    "XXXII - Deixar de cumprir determinação de aluno em função de chefia;",
    "XXXIII - Cumprir parcialmente ou deturpar ordem recebida;",
    "XXXIV - Retirar-se do local de instrução, sem permissão;",
    "XXXV - Tomar medidas de ordem administrativa ou disciplinar fora de sua esfera de atribuições;",
    "XXXVI - Deixar, quando em função de comando, de encaminhar ao escalão superior solicitação que deva ser solucionada;",
    "XXXVII - Deixar de colocar a arma na arrecadação tão logo cesse a instrução ou serviço;",
    "XLI - Utilizar material não permitido em instrução ou serviço;",
    "XLII - Determinar formatura ou deslocamento de tropa sem autorização;",
    "XLIII - Perturbar, através de conversa ou ruído, o local de instrução ou de estudo;",
    "XLIV - Comentar com pessoas estranhas ao Corpo de Alunos, assuntos que só dizem respeito ao público interno;",
    "XLV - Permitir que o aluno, durante o cumprimento de punição, afaste-se do local determinado;",
    "XLVI - Deixar, quando de hora ou turno de serviço, de tomar providências que exijam sua atuação;",
    "XLVII - Apresentar atitude comportamental que prejudique o bom desempenho de seu serviço;",
    "XLVIII - Transitar fardado fora da área do quartel, sem estar devidamente autorizado;",
    "XLIX - Deixar de comparecer ou de permanecer em local em que seja determinada a sua presença;",
    "LII - Deixar de confeccionar parte escrita quando presenciar ou tiver conhecimento de qualquer irregularidade;",
    "LIII - Promover atividades comerciais nas dependências da EsFAS sem autorização;",
    "LIV - Viajar para fora do Estado do Rio Grande do Sul sem comunicar o Comando de Alunos;",
    "LV - Afastar-se do quartel sem estar autorizado;",
    "LVI - Deixar o aluno em férias escolares ou dispensa, de regressar no dia marcado à EsFAS;",
    "LVII - Assumir compromisso em nome do Corpo de Alunos ou da EsFAS sem autorização;",
    "LVIII - Demonstrar descontrole financeiro, afetando o conceito da Corporação perante a comunidade;",
    "LIX - Deixar de saldar, ou não fazê-lo em tempo hábil, compromissos financeiros com a administração da EsFAS;",
    "LX - Afastar-se do seu local de serviço, quando em seu quarto de hora, desde que não se constitua abandono;",
    "XI - Danificar material da fazenda estadual;",
    "LXV - Portar ou utilizar telefone móvel fora dos horários autorizados pelo Corpo de Aluno;",
    "LXVI - Transitar no complexo da EsFAS trajando uniforme em desacordo com o previsto;",
    "LXVII - Deixar de fazer a manutenção do fuzil, quando escalado ou determinado;",
    "LXVIII - Deixar de ter nos seus armários, todos os fardamentos previstos no enxoval do CTSP;",
    "LXIX - Sair da sala de aula, mesmo que com autorização, por motivo fútil;",
    "LXX - Transitar nas dependências do Corpo de Alunos nos horários de sala de aula;",
    "LXXI - Levar pessoa estranha às dependências do Corpo de Alunos sem prévia autorização;",
    "LXXII - Utilizar qualquer dependência da EsFAS, fora do horário de expediente, sem prévia autorização;",
    "LXXIII - Realizar instrução ou atividade física se houver determinação médica em contrário."
]

@justica_bp.route('/')
@login_required
def index():
    """Página principal de Justiça e Disciplina."""
    processos = JusticaService.get_processos_para_usuario(current_user)
    
    processos_em_andamento = [p for p in processos if p.status != 'Finalizado']
    processos_finalizados = [p for p in processos if p.status == 'Finalizado']

    return render_template(
        'justica/index.html',
        em_andamento=processos_em_andamento,
        finalizados=processos_finalizados,
        fatos_predefinidos=FATOS_PREDEFINIDOS # Passa a lista para o template
    )

@justica_bp.route('/analise')
@login_required
@admin_or_programmer_required
def analise():
    """Página de análise de dados e gráficos."""
    dados_analise = JusticaService.get_analise_disciplinar_data()
    return render_template('justica/analise.html', dados=dados_analise)


@justica_bp.route('/finalizar/<int:processo_id>', methods=['POST'])
@login_required
@admin_or_programmer_required
def finalizar_processo(processo_id):
    decisao = request.form.get('decisao_final')
    fundamentacao = request.form.get('fundamentacao')
    detalhes_sancao = request.form.get('detalhes_sancao')

    if not decisao or not fundamentacao:
        flash('É necessário selecionar uma decisão e preencher a fundamentação.', 'danger')
        return redirect(url_for('justica.index'))
    
    if decisao in ['Advertência', 'Repreensão'] and not detalhes_sancao:
        flash('Para Advertência ou Repreensão, o campo de detalhes da sanção é obrigatório.', 'danger')
        return redirect(url_for('justica.index'))

    success, message = JusticaService.finalizar_processo(processo_id, decisao, fundamentacao, detalhes_sancao)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('justica.index'))
    
# ... (o resto do arquivo pode permanecer como está)
@justica_bp.route('/novo', methods=['POST'])
@login_required
@admin_or_programmer_required
def novo_processo():
    aluno_id = request.form.get('aluno_id')
    fato = request.form.get('fato')
    observacao = request.form.get('observacao')

    if not aluno_id or not fato:
        flash('Aluno e Fato Constatado são obrigatórios.', 'danger')
        return redirect(url_for('justica.index'))

    success, message = JusticaService.criar_processo(fato, observacao, int(aluno_id), current_user.id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/dar-ciente/<int:processo_id>', methods=['POST'])
@login_required
def dar_ciente(processo_id):
    success, message = JusticaService.registrar_ciente(processo_id, current_user)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/enviar-defesa/<int:processo_id>', methods=['POST'])
@login_required
def enviar_defesa(processo_id):
    defesa = request.form.get('defesa')
    if not defesa:
        flash('O texto da defesa não pode estar vazio.', 'danger')
        return redirect(url_for('justica.index'))
    
    success, message = JusticaService.enviar_defesa(processo_id, defesa, current_user)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/deletar/<int:processo_id>', methods=['POST'])
@login_required
@admin_or_programmer_required
def deletar_processo(processo_id):
    success, message = JusticaService.deletar_processo(processo_id)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('justica.index'))

@justica_bp.route('/api/alunos')
@login_required
@admin_or_programmer_required
def api_get_alunos():
    search = request.args.get('q', '').lower()
    query = (
        select(Aluno)
        .join(User)
        .where(
            or_(
                User.nome_completo.ilike(f'%{search}%'),
                User.matricula.ilike(f'%{search}%')
            )
        )
        .order_by(User.nome_completo)
        .limit(20)
    )
    alunos = db.session.scalars(query).all()
    results = [{'id': a.id, 'text': f"{a.user.nome_completo} ({a.user.matricula})"} for a in alunos]
    return jsonify(results)

@justica_bp.route('/api/aluno-details/<int:aluno_id>')
@login_required
@admin_or_programmer_required
def api_get_aluno_details(aluno_id):
    aluno = db.session.get(Aluno, aluno_id)
    if not aluno or not aluno.user:
        return jsonify({'error': 'Aluno não encontrado'}), 404
    
    details = {
        'posto_graduacao': aluno.user.posto_graduacao or 'POSTO/GRADUAÇÃO',
        'matricula': aluno.user.matricula or 'MATRÍCULA',
        'nome_completo': aluno.user.nome_completo or 'NOME DO ALUNO'
    }
    return jsonify(details)

@justica_bp.route('/exportar', methods=['GET', 'POST'])
@login_required
@admin_or_programmer_required
def exportar_selecao():
    try:
        locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, '')

    if request.method == 'POST':
        processo_ids = request.form.getlist('processo_ids')
        if not processo_ids:
            flash('Nenhum processo selecionado para exportar.', 'warning')
            return redirect(url_for('justica.exportar_selecao'))

        processos = JusticaService.get_processos_por_ids([int(pid) for pid in processo_ids])
        
        rendered_html = render_template('justica/export_bi_template.html', processos=processos)
        
        return Response(
            rendered_html,
            mimetype="application/msword",
            headers={"Content-disposition": "attachment; filename=export_processos_BI.doc"}
        )
    
    processos_finalizados = JusticaService.get_finalized_processos()
    return render_template('justica/exportar_selecao.html', processos=processos_finalizados)