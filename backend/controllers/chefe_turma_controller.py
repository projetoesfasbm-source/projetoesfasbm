from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import date, datetime, timedelta
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import joinedload 
import re

from backend.models.database import db
from backend.models.horario import Horario
from backend.models.aluno import Aluno
from backend.models.diario_classe import DiarioClasse
from backend.models.frequencia import FrequenciaAluno
from backend.models.semana import Semana
from backend.models.disciplina import Disciplina
from backend.models.turma import Turma

chefe_bp = Blueprint('chefe', __name__, url_prefix='/chefe')

def get_variacoes_nome_turma(nome_original):
    """Gera variações comuns de nomes de turma para busca flexível."""
    variacoes = {nome_original}
    try:
        match = re.search(r'(\d+)', nome_original)
        if match:
            num_str = match.group(1)
            num_int = int(num_str)
            variacoes.add(f"Turma {num_str}")
            variacoes.add(f"Turma {num_int}")
            variacoes.add(f"{num_str}º Pelotão")
            variacoes.add(f"{num_int}º Pelotão")
    except Exception:
        pass
    return list(variacoes)

def verify_chefe_permission():
    try:
        if not current_user.is_authenticated or not current_user.aluno_profile:
            return None
        return current_user.aluno_profile
    except Exception:
        return None

def get_dia_semana_str(data_obj):
    dias = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
    return dias[data_obj.weekday()]

@chefe_bp.route('/painel')
@login_required
def painel():
    try:
        aulas_agrupadas = []
        aluno = verify_chefe_permission()
        
        if not aluno or not aluno.turma_id:
            flash("Acesso restrito ou aluno sem turma.", "danger")
            return redirect(url_for('main.index'))

        # DATA CORTE: Hoje (para não mostrar futuro)
        data_hoje = date.today()
        
        # JANELA DE BUSCA: Olha 30 dias para trás para achar pendências
        data_inicio_busca = data_hoje - timedelta(days=30)
        
        # 1. Carrega TODAS as semanas que tocam essa janela de tempo
        semanas_no_periodo = db.session.query(Semana).filter(
            Semana.data_fim >= data_inicio_busca,
            Semana.data_inicio <= data_hoje
        ).all()

        if not semanas_no_periodo:
            # Se não tem semanas cadastradas, não tem como ter aula
            return render_template('chefe/painel.html', aluno=aluno, aulas_agrupadas=[], data_selecionada=data_hoje, erro_semana=True)

        variacoes_nome = get_variacoes_nome_turma(aluno.turma.nome)

        # 2. Carrega TODOS os horários dessas semanas vinculados à turma
        ids_semanas = [s.id for s in semanas_no_periodo]
        
        todos_horarios = db.session.query(Horario).join(Horario.disciplina).filter(
            Horario.semana_id.in_(ids_semanas),
            or_(
                Disciplina.turma_id == aluno.turma_id,
                Horario.pelotao == aluno.turma.nome,
                Horario.pelotao.in_(variacoes_nome)
            )
        ).options(
            joinedload(Horario.disciplina),
            joinedload(Horario.instrutor)
        ).order_by(Horario.periodo).all()

        # Organiza horários por (semana_id, dia_semana) para acesso rápido
        mapa_horarios = {} # Chave: (semana_id, 'Segunda') -> [lista de horarios]
        for h in todos_horarios:
            chave = (h.semana_id, h.dia_semana)
            if chave not in mapa_horarios:
                mapa_horarios[chave] = []
            mapa_horarios[chave].append(h)

        # 3. Carrega TODOS os diários já feitos neste intervalo (para saber o que já foi concluído)
        diarios_feitos = db.session.query(DiarioClasse).filter(
            DiarioClasse.turma_id == aluno.turma_id,
            DiarioClasse.data_aula >= data_inicio_busca,
            DiarioClasse.data_aula <= data_hoje
        ).all()

        # Mapa de conclusão: (data_aula, disciplina_id)
        # Se existir um diário para essa data/disciplina, consideramos "iniciado/concluido"
        # Otimização: Se quiser checar por período exato, adicionar periodo na chave
        mapa_concluidos = set()
        for d in diarios_feitos:
            mapa_concluidos.add((d.data_aula, d.disciplina_id))

        grupos_dict = {}

        # 4. ITERAÇÃO DIA A DIA (Do passado até hoje)
        # Varre do dia mais antigo (inicio busca) até hoje
        delta_days = (data_hoje - data_inicio_busca).days + 1
        
        for i in range(delta_days):
            dia_corrente = data_inicio_busca + timedelta(days=i)
            dia_str_corrente = get_dia_semana_str(dia_corrente)

            # Acha a semana que engloba este dia
            semana_deste_dia = next((s for s in semanas_no_periodo if s.data_inicio <= dia_corrente <= s.data_fim), None)
            
            if not semana_deste_dia:
                continue # Dia fora de qualquer semana letiva

            # Pega os horários previstos para este dia/semana
            horarios_do_dia = mapa_horarios.get((semana_deste_dia.id, dia_str_corrente), [])

            for h in horarios_do_dia:
                chave_conclusao = (dia_corrente, h.disciplina_id)
                ja_feito = chave_conclusao in mapa_concluidos
                
                # Regra de Exibição:
                # 1. Se é hoje: Mostra sempre (Pendente ou Concluido)
                # 2. Se é passado: Mostra APENAS se Pendente (não feito)
                if dia_corrente < data_hoje and ja_feito:
                    continue 

                status_final = 'concluido' if ja_feito else 'pendente'

                # Chave única para agrupar no painel
                chave_grupo = (dia_corrente, h.disciplina_id)

                if chave_grupo not in grupos_dict:
                    nome_instrutor = "N/A"
                    if h.instrutor:
                        if hasattr(h.instrutor, 'user') and h.instrutor.user:
                            nome_instrutor = h.instrutor.user.nome_de_guerra or h.instrutor.user.nome_completo
                        elif hasattr(h.instrutor, 'nome_guerra'):
                            nome_instrutor = h.instrutor.nome_guerra

                    grupos_dict[chave_grupo] = {
                        'data_aula': dia_corrente,
                        'data_str': dia_corrente.strftime('%d/%m/%Y'),
                        'dia_semana': dia_str_corrente,
                        'disciplina': h.disciplina,
                        'nome_instrutor': nome_instrutor,
                        'horarios_reais': [], 
                        'periodos_expandidos': [], 
                        'status': status_final,
                        'primeiro_horario_id': h.id,
                        # Chave de ordenação: Data (recente primeiro ou antiga primeiro?) -> 
                        # Vamos ordenar cronologicamente: Antiga -> Nova
                        'sort_key': f"{dia_corrente.strftime('%Y%m%d')}_{h.periodo:02d}"
                    }
                
                # Se algum item do grupo ainda não foi feito, marca o grupo como pendente (caso haja mix)
                if not ja_feito:
                    grupos_dict[chave_grupo]['status'] = 'pendente'

                grupos_dict[chave_grupo]['horarios_reais'].append(h)
                duracao = h.duracao if h.duracao and h.duracao > 0 else 1
                for k in range(duracao):
                    grupos_dict[chave_grupo]['periodos_expandidos'].append(h.periodo + k)

        # Ordenação final e lista
        # Ordenando por data crescente (antigas primeiro)
        lista_ordenada = sorted(grupos_dict.values(), key=lambda x: x['sort_key'])
        
        for g in lista_ordenada:
            g['periodos'] = sorted(list(set(g['periodos_expandidos'])))
            aulas_agrupadas.append(g)

        return render_template('chefe/painel.html', aluno=aluno, aulas_agrupadas=aulas_agrupadas, data_selecionada=data_hoje, erro_semana=False)

    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"Erro no painel: {str(e)}", "danger")
        return redirect(url_for('main.index'))

@chefe_bp.route('/registrar/<int:primeiro_horario_id>', methods=['GET', 'POST'])
@login_required
def registrar_aula(primeiro_horario_id):
    try:
        aluno_chefe = verify_chefe_permission()
        if not aluno_chefe: return redirect(url_for('main.index'))

        # A data deve vir na URL para sabermos se estamos registrando aula de ontem ou de hoje
        data_str = request.args.get('data')
        if not data_str:
            flash("Data da aula não identificada.", "warning")
            return redirect(url_for('chefe.painel'))
            
        data_aula = datetime.strptime(data_str, '%Y-%m-%d').date()

        # Busca o horário base SEM filtro excessivo de escola no join (confiamos no aluno_chefe.turma_id)
        horario_base = db.session.query(Horario).join(Horario.disciplina).filter(
            Horario.id == primeiro_horario_id
        ).first()

        if not horario_base: 
            flash("Horário não encontrado.", "danger")
            return redirect(url_for('chefe.painel'))
            
        # Validação extra de segurança: A disciplina pertence à turma do aluno?
        if horario_base.disciplina.turma_id != aluno_chefe.turma_id and horario_base.pelotao != aluno_chefe.turma.nome:
             flash("Este horário não pertence à sua turma.", "danger")
             return redirect(url_for('chefe.painel'))

        variacoes_nome = get_variacoes_nome_turma(aluno_chefe.turma.nome)
        
        # Busca irmãos (outros tempos da mesma aula)
        horarios_db = db.session.query(Horario).join(Horario.disciplina).filter(
            Horario.semana_id == horario_base.semana_id,
            Horario.dia_semana == horario_base.dia_semana,
            Horario.disciplina_id == horario_base.disciplina_id,
            or_(
                Disciplina.turma_id == aluno_chefe.turma_id,
                Horario.pelotao == aluno_chefe.turma.nome,
                Horario.pelotao.in_(variacoes_nome)
            )
        ).order_by(Horario.periodo).all()

        horarios_expandidos = []
        for h in horarios_db:
            duracao = h.duracao if h.duracao and h.duracao > 0 else 1
            for i in range(duracao):
                p = h.periodo + i
                horarios_expandidos.append({'periodo': p, 'horario_pai_id': h.id, 'obj': h})
        
        horarios_expandidos.sort(key=lambda x: x['periodo'])
        alunos_turma = db.session.query(Aluno).filter_by(turma_id=aluno_chefe.turma_id).order_by(Aluno.num_aluno).all()

        if request.method == 'POST':
            try:
                # Verificação simples de duplicidade
                existe = db.session.query(DiarioClasse).filter_by(
                    data_aula=data_aula,
                    turma_id=aluno_chefe.turma_id,
                    disciplina_id=horario_base.disciplina_id
                ).first()
                
                if existe:
                    flash("Esta aula já foi registrada anteriormente.", "warning")
                    return redirect(url_for('chefe.painel'))

                for h_virt in horarios_expandidos:
                    periodo_atual = h_virt['periodo']
                    horario_pai = h_virt['obj']

                    novo_diario = DiarioClasse(
                        data_aula=data_aula, # Usa a data correta (passado ou presente)
                        turma_id=aluno_chefe.turma_id,
                        disciplina_id=horario_pai.disciplina_id,
                        responsavel_id=current_user.id,
                        observacoes=request.form.get('observacoes'),
                        conteudo_ministrado=request.form.get('conteudo'),
                        periodo=periodo_atual
                    )
                    db.session.add(novo_diario)
                    db.session.flush()

                    for aluno in alunos_turma:
                        key = f"presenca_{aluno.id}_{periodo_atual}"
                        presente = (key in request.form)
                        db.session.add(FrequenciaAluno(diario_id=novo_diario.id, aluno_id=aluno.id, presente=presente))
                    
                db.session.commit()
                flash(f"Aula do dia {data_aula.strftime('%d/%m')} registrada com sucesso!", "success")
                return redirect(url_for('chefe.painel'))
                
            except Exception as e:
                db.session.rollback()
                flash(f"Erro ao salvar: {str(e)}", "danger")

        nome_instrutor = "N/A"
        if horario_base.instrutor:
             if hasattr(horario_base.instrutor, 'user') and horario_base.instrutor.user:
                 nome_instrutor = horario_base.instrutor.user.nome_de_guerra
        
        return render_template('chefe/registrar.html', 
                               horarios=horarios_expandidos, 
                               disciplina=horario_base.disciplina, 
                               nome_instrutor=nome_instrutor, 
                               alunos=alunos_turma, 
                               data_aula=data_aula) # Passa a data correta para o template exibir

    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"Erro: {str(e)}", "danger")
        return redirect(url_for('chefe.painel'))

@chefe_bp.route('/debug')
@login_required
def debug_screen():
    return "Debug desativado em produção."