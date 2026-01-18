import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
from backend.models.aluno import Aluno
from backend.models.turma import Turma
from backend.models.school import School
from backend.models.processo_disciplina import ProcessoDisciplina, StatusProcesso
from backend.models.discipline_rule import DisciplineRule
from backend.services.avaliacao_service import AvaliacaoService

app = create_app()

def simular_preparacao_formulario():
    """
    Este teste simula o que o CONTROLLER deveria fazer antes de abrir a tela 'nova.html'.
    Ele mapeia as infrações para os atributos da FADA.
    """
    with app.app_context():
        print("\n=== SIMULAÇÃO: PREPARAÇÃO DO FORMULÁRIO DE AVALIAÇÃO INTELIGENTE ===\n")
        
        # 1. SETUP (Criar cenário temporário)
        try:
            # Escola e Turma (CORREÇÃO: Usando 'nome' em vez de 'name')
            escola = School(nome="Escola CSPM Teste", npccal_type="cspm")
            db.session.add(escola)
            db.session.flush()
            
            turma = Turma(nome="Turma Bravo", school_id=escola.id)
            db.session.add(turma)
            db.session.flush()
            
            aluno = Aluno(nome_completo="Cadete Exemplo", nome_guerra="Exemplo", turma_id=turma.id)
            db.session.add(aluno)
            db.session.flush()

            # 2. CENÁRIO DE INFRAÇÕES
            # Vamos criar 2 regras vinculadas a atributos específicos da FADA
            # Lista de Critérios (Indices baseados em AvaliacaoService.CRITERIOS_FADA):
            # Índice 11: Assiduidade
            # Índice 12: Pontualidade
            
            regras = [
                DisciplineRule(
                    codigo="001", descricao="Chegar Atrasado", 
                    pontos=0.5, # Média
                    atributo_fada_id=12, # Pontualidade (Indice 11 na lista 0-based se for o 12º item)
                    npccal_type="cspm"
                ),
                DisciplineRule(
                    codigo="002", descricao="Faltar ao serviço", 
                    pontos=1.0, # Grave
                    atributo_fada_id=11, # Assiduidade
                    npccal_type="cspm"
                )
            ]
            db.session.add_all(regras)
            db.session.flush()

            # Criar Processos Finalizados para o Aluno
            processos = [
                ProcessoDisciplina(
                    aluno_id=aluno.id, regra_id=regras[0].id, pontos=0.5,
                    status=StatusProcesso.FINALIZADO, data_decisao=datetime.now(),
                    fato_constatado="Chegou atrasado na formatura."
                ),
                ProcessoDisciplina(
                    aluno_id=aluno.id, regra_id=regras[1].id, pontos=1.0,
                    status=StatusProcesso.FINALIZADO, data_decisao=datetime.now(),
                    fato_constatado="Faltou ao serviço de guarda."
                )
            ]
            db.session.add_all(processos)
            db.session.flush()

            # 3. LÓGICA PROPOSTA (O que precisa ir para o Controller)
            print(f"Aluno: {aluno.nome_completo}")
            print("-" * 60)
            
            # Mapeamento de descontos por Atributo FADA
            # Estrutura: { index_atributo: { 'desconto': float, 'motivos': list } }
            mapa_fada = {}
            
            # Pesos de desconto conforme PDF (Art 125)
            # Simplificação para teste: Leve=0.25, Média=0.5, Grave=1.0
            def get_peso_desconto(pontos):
                if pontos >= 1.0: return 1.0 # Grave
                if pontos >= 0.5: return 0.5 # Média
                return 0.25 # Leve

            # Simulando busca no banco
            procs_aluno = db.session.scalars(
                db.select(ProcessoDisciplina)
                .where(ProcessoDisciplina.aluno_id == aluno.id, ProcessoDisciplina.status == 'Finalizado')
            ).all()

            for p in procs_aluno:
                regra = db.session.get(DisciplineRule, p.regra_id)
                if regra and regra.atributo_fada_id:
                    # Ajuste de índice (Se no banco começa em 1, no array Python começa em 0)
                    # Vamos assumir que atributo_fada_id 1 = índice 0
                    idx = regra.atributo_fada_id - 1 
                    
                    desconto = get_peso_desconto(p.pontos)
                    
                    if idx not in mapa_fada:
                        mapa_fada[idx] = {'nota_maxima': 10.0, 'motivos': []}
                    
                    mapa_fada[idx]['nota_maxima'] -= desconto
                    mapa_fada[idx]['motivos'].append(f"{regra.descricao} (-{desconto})")

            # 4. EXIBIÇÃO DO RESULTADO PARA O FRONTEND
            print("DADOS QUE O FRONTEND RECEBERIA PARA BLOQUEAR O FORMULÁRIO:")
            
            criterios = AvaliacaoService.CRITERIOS_FADA
            for i, nome_criterio in enumerate(criterios):
                dados = mapa_fada.get(i)
                if dados:
                    print(f"\n[BLOQUEIO] Atributo: {nome_criterio}")
                    print(f"   Nota Máxima Permitida: {dados['nota_maxima']}")
                    print(f"   Motivos: {', '.join(dados['motivos'])}")
                else:
                    # Atributos sem infração continuam livres (10.0)
                    pass

            print("\n" + "-" * 60)
            print("Conclusão: É possível gerar este mapa antes de renderizar 'nova.html'.")
            
            db.session.rollback()

        except Exception as e:
            print(f"ERRO DE EXECUÇÃO: {e}")
            # Importante para ver o erro completo se houver outro
            import traceback
            traceback.print_exc()
            db.session.rollback()

if __name__ == "__main__":
    simular_preparacao_formulario()