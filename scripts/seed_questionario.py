import sys
import os
from dotenv import load_dotenv
from sqlalchemy import select

# 1. Configuração do Ambiente e Caminhos
# Adiciona o diretório raiz do projeto ao path do Python para encontrar os módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Carrega as variáveis de ambiente (como a do banco de dados) do arquivo .env na raiz
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))


# 2. Importações da Aplicação
# Importa a função que cria a aplicação e os modelos do banco
from backend.app import create_app
from backend.models.database import db
from backend.models.questionario import Questionario
from backend.models.pergunta import Pergunta
from backend.models.opcao_resposta import OpcaoResposta


# 3. Dados a serem inseridos
DADOS_QUESTIONARIO = {
    "titulo": "Avaliação Inicial CTSP",
    "perguntas": [
        {"texto": "Idade?", "tipo": "unica", "opcoes": ["Até 30 anos", "De 31 a 35 anos", "De 36 a 40 anos", "De 41 a 45 anos", "Acima de 45 anos"]},
        {"texto": "De onde você é? (cidade/estado)", "tipo": "texto_livre", "opcoes": []},
        {"texto": "Como é a sua estrutura familiar?", "tipo": "unica", "opcoes": ["Moro sozinho(a)", "Moro com cônjuge/companheiro(a)", "Moro com cônjuge/companheiro(a) e filho(s)", "Moro com meus pais e/ou irmãos", "Outra configuração (família estendida, etc.)"]},
        {"texto": "Qual foi o apoio da sua família na sua decisão de fazer o CTSP?", "tipo": "unica", "opcoes": ["Nenhum apoio, foram contra a decisão.", "Pouco apoio, demonstraram indiferença.", "Apoio moderado, aceitaram a decisão.", "Alto apoio, foram grandes incentivadores.", "Apoio total, participaram ativamente e me motivaram."]},
        {"texto": "Qual foi o seu nível de escolaridade?", "tipo": "unica", "opcoes": ["Ensino Médio Completo", "Ensino Superior Incompleto", "Ensino Superior Completo", "Pós-Graduação (Especialização)", "Pós-Graduação (Mestrado/Doutorado)"]},
        {"texto": "Quais foram os maiores desafios educacionais que enfrentou?", "tipo": "multipla", "opcoes": ["Conciliar os estudos com a escala de serviço", "Dificuldades financeiras", "Falta de tempo para se dedicar aos estudos", "Dificuldade de acesso a materiais ou instituições de ensino", "Questões familiares ou pessoais", "Não enfrentei desafios significativos", "Outro"]},
        {"texto": "Trabalha em qual Batalhão?", "tipo": "texto_livre", "opcoes": []},
        {"texto": "Onde está lotado? (Ex: Pelotão, Companhia, Seção Administrativa)", "tipo": "texto_livre", "opcoes": []},
        {"texto": "Quais experiências possui no administrativo da Brigada?", "tipo": "multipla", "opcoes": ["Nenhuma experiência administrativa", "P1 (Seção de Pessoal)", "P2 (Seção de Inteligência)", "P3 (Seção de Operações)", "P4 (Seção de Logística e Patrimônio)", "P5 (Comunicação Social)", "Funções de Secretária ou Auxiliar", "Outra área"]},
        {"texto": "Já atendeu ocorrência que houve confronto policial?", "tipo": "unica", "opcoes": ["Sim", "Não"]},
        {"texto": "Já atendeu ocorrência em que algum colega ficou ferido/morreu?", "tipo": "unica", "opcoes": ["Sim", "Não"]},
        {"texto": "Já causou lesão ou morte em decorrência de atendimento de ocorrência?", "tipo": "unica", "opcoes": ["Sim", "Não"]},
        {"texto": "Após o atendimento dessas ocorrências (confronto, colega ferido, etc.), você foi encaminhado para atendimento psicológico?", "tipo": "unica", "opcoes": ["Sim, fui encaminhado e participei do atendimento.", "Sim, fui encaminhado mas optei por não participar.", "Não, não fui encaminhado pela corporação.", "Busquei ajuda por iniciativa própria.", "Não se aplica (nunca vivenciei tais situações)."]},
        {"texto": "O que te motivou a fazer o CTSP?", "tipo": "multipla", "opcoes": ["Progressão e ascensão na carreira", "Melhoria salarial", "Oportunidade de assumir uma posição de liderança", "Aprofundar meus conhecimentos técnicos e táticos", "Ser uma referência para os policiais mais novos", "Estabilidade e planejamento de futuro", "Outro motivo"]},
        {"texto": "Quais são seus objetivos como Sargento?", "tipo": "multipla", "opcoes": ["Liderar e desenvolver minha equipe", "Atuar na gestão e planejamento operacional", "Ser uma referência técnica na minha área de atuação", "Melhorar os processos e rotinas do meu setor", "Contribuir para a formação de novos policiais", "Buscar novas especializações dentro da Brigada Militar"]},
        {"texto": "Como você se vê daqui a 5 anos?", "tipo": "texto_livre", "opcoes": []},
        {"texto": "Quais valores são mais importantes para você? (Escolha até 3)", "tipo": "multipla", "opcoes": ["Hierarquia e Disciplina", "Honestidade e Integridade", "Coragem e Bravura", "Justiça e Imparcialidade", "Lealdade e Espírito de Corpo", "Família", "Respeito ao próximo", "Comprometimento com o serviço"]},
        {"texto": "Como você lida com situações de conflito ou pressão?", "tipo": "unica", "opcoes": ["Mantenho a calma e foco estritamente na técnica e procedimento padrão.", "Busco a comunicação e o diálogo para desescalar a situação.", "Confio na minha intuição e experiência para tomar decisões rápidas.", "Apoio-me na minha equipe, delegando e confiando nos colegas.", "Sinto a pressão, mas consigo agir de forma controlada."]},
        {"texto": "O que significa 'liderança' para você?", "tipo": "unica", "opcoes": ["É dar o exemplo, inspirando a equipe através da própria conduta.", "É comandar, garantindo que as ordens sejam cumpridas com disciplina e eficiência.", "É cuidar da equipe, provendo os recursos e o bem-estar necessários para o cumprimento da missão.", "É alcançar os resultados, utilizando as melhores estratégias e motivando o time para o objetivo."]},
        {"texto": "Como você cuida da sua saúde física e mental? (Marque todas as aplicáveis)", "tipo": "multipla", "opcoes": ["Pratico atividades físicas regularmente", "Busco ter uma alimentação balanceada", "Priorizo minhas noites de sono", "Tenho hobbies e momentos de lazer (pesca, leitura, etc.)", "Passo tempo de qualidade com família e amigos", "Procuro acompanhamento médico/psicológico quando necessário", "Atualmente, não tenho uma rotina de autocuidado"]},
        {"texto": "Faz ou já fez acompanhamento psiquiátrico/psicológico?", "tipo": "unica", "opcoes": ["Sim, faço acompanhamento atualmente.", "Sim, já fiz no passado.", "Não, mas sinto que seria benéfico.", "Não, nunca senti necessidade.", "Prefiro não responder."]},
        {"texto": "Pratica esportes ou atividades físicas regularmente?", "tipo": "unica", "opcoes": ["Sim, 5 vezes por semana ou mais", "Sim, de 3 a 4 vezes por semana", "Sim, de 1 a 2 vezes por semana", "Sim, esporadicamente (menos de 1 vez por semana)", "Não pratico"]},
        {"texto": "Como lida com o estresse do dia a dia? (Marque as principais formas)", "tipo": "multipla", "opcoes": ["Praticando esportes ou atividades físicas", "Conversando com o cônjuge, familiares ou amigos", "Dedicando tempo a um hobby", "Através da religião ou espiritualidade", "Assistindo a filmes/séries ou jogando videogame", "Simplesmente tento não pensar no assunto", "Outra forma"]},
        {"texto": "Você fuma?", "tipo": "unica", "opcoes": ["Sim, diariamente", "Sim, socialmente/ocasionalmente", "Não, mas já fui fumante", "Não, nunca fumei"]},
        {"texto": "Possui alguma doença crônica diagnosticada (ex: hipertensão, diabetes)?", "tipo": "multipla", "opcoes": ["Sim", "Não", "Quais"]},
        {"texto": "Faz uso de alguma medicação de forma contínua?", "tipo": "multipla", "opcoes": ["Sim", "Não", "Quais"]},
    ]
}

def popular_questionario_db():
    """
    Função principal que se conecta ao banco e insere os dados.
    """
    titulo = DADOS_QUESTIONARIO['titulo']
    
    # Verifica se o questionário já existe para evitar duplicação
    questionario_existente = db.session.scalar(select(Questionario).where(Questionario.titulo == titulo))
    if questionario_existente:
        print(f"O questionário '{titulo}' já existe na base de dados. Nenhuma ação foi tomada.")
        return

    print(f"Criando o questionário: '{titulo}'...")
    try:
        # Cria o objeto principal do questionário
        novo_questionario = Questionario(titulo=titulo)
        db.session.add(novo_questionario)
        db.session.flush() # Garante que o novo_questionario.id esteja disponível

        # Itera sobre cada pergunta nos dados
        for pergunta_info in DADOS_QUESTIONARIO['perguntas']:
            nova_pergunta = Pergunta(
                texto=pergunta_info['texto'],
                questionario_id=novo_questionario.id,
                tipo=pergunta_info['tipo']
            )
            db.session.add(nova_pergunta)
            db.session.flush() # Garante que a nova_pergunta.id esteja disponível

            # Adiciona as opções de resposta para a pergunta
            for opcao_texto in pergunta_info['opcoes']:
                opcao = OpcaoResposta(texto=opcao_texto, pergunta_id=nova_pergunta.id)
                db.session.add(opcao)

        # Se tudo correu bem, salva todas as alterações no banco de dados
        db.session.commit()
        print("Questionário criado com sucesso!")

    except Exception as e:
        # Em caso de qualquer erro, desfaz todas as alterações
        db.session.rollback()
        print(f"Ocorreu um erro ao criar o questionário: {e}")


# 4. Ponto de Entrada do Script
if __name__ == '__main__':
    # Cria a instância da aplicação Flask para ter o contexto correto
    app = create_app()
    # Executa a função de popular o banco dentro do contexto da aplicação
    with app.app_context():
        popular_questionario_db()