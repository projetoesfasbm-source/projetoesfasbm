import sys
import os
from datetime import datetime, timedelta

# Adiciona o diretório atual ao path para importar o backend
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
from backend.models.user import User  # Import necessário
from backend.models.aluno import Aluno
from backend.models.turma import Turma
from backend.models.school import School
from backend.models.processo_disciplina import ProcessoDisciplina, StatusProcesso
from backend.models.discipline_rule import DisciplineRule
from backend.services.avaliacao_service import AvaliacaoService

app = create_app()

def simular_preparacao_formulario():
    with app.app_context():
        print("\n=== SIMULAÇÃO: PREPARAÇÃO DO FORMULÁRIO DE AVALIAÇÃO INTELIGENTE ===\n")
        
        try:
            # 1. SETUP - Escola e Turma
            escola = School(nome="Escola CSPM Teste", npccal_type="cspm")
            db.session.add(escola)
            db.session.flush()
            
            turma = Turma(nome="Turma Bravo", ano="2026", school_id=escola.id)
            db.session.add(turma)
            db.session.flush()
            
            # 2. SETUP - Usuário e Aluno (CORREÇÃO AQUI)
            # Primeiro cria o usuário (onde ficam o nome e matricula)
            user = User(
                matricula="999999",
                nome_completo="Cadete Exemplo", 
                nome_de_guerra="Exemplo",
                role="aluno"
            )
            db.session.add(user)
            db.session.flush() # Para gerar o user.id

            # Depois cria o perfil de aluno vinculado
            aluno = Aluno(
                user_id=user.id,
                opm="ESFAS",
                turma_id=turma.id
            )
            db.session.add(aluno)
            db.session.flush()

            # 3. CENÁRIO DE INFRAÇÕES
            # Regras vinculadas (FADA ID 12 = Pontualidade, ID 11 = Assiduidade)
            regras = [
                DisciplineRule(
                    codigo="001", descricao="Chegar Atrasado", 
                    pontos=0.5, 
                    atributo_fada_id=12,
                    npccal_type="cspm"
                ),
                DisciplineRule(
                    codigo="002", descricao="Faltar ao serviço", 
                    pontos=1.0, 
                    atributo_fada_id=11,
                    npccal_type="cspm"
                )
            ]
            db.session.add_all(regras)
            db.session.flush()

            processos = [
                ProcessoDisciplina(
                    aluno_id=aluno.id, relator_id=user.id, regra_id=regras[0].id, pontos=0.5,
                    status=StatusProcesso.FINALIZADO, data_decisao=datetime.now(),
                    fato_constatado="Chegou atrasado na formatura."
                ),
                ProcessoDisciplina(
                    aluno_id=aluno.id, relator_id=user.id, regra_id=regras[1].id, pontos=1.0,
                    status=StatusProcesso.FINALIZADO, data_decisao=datetime.now(),
                    fato_constatado="Faltou ao serviço de guarda."
                )
            ]
            db.session.add_all(processos)
            db.session.flush()

            # 4. LÓGICA DE CÁLCULO
            print(f"Aluno: {user.nome_completo}")
            print("-" * 60)
            
            mapa_fada = {}
            
            def get_peso_desconto(pontos):
                if pontos >= 1.0: return 1.0
                if pontos >= 0.5: return 0.5
                return 0.25

            procs_aluno = db.session.scalars(
                db.select(ProcessoDisciplina)
                .where(ProcessoDisciplina.aluno_id == aluno.id, ProcessoDisciplina.status == 'Finalizado')
            ).all()

            for p in procs_aluno:
                regra = db.session.get(DisciplineRule, p.regra_id)
                if regra and regra.atributo_fada_id:
                    # Ajuste de índice (Assumindo que atributo_fada_id 1 = índice 0)
                    idx = regra.atributo_fada_id - 1 
                    desconto = get_peso_desconto(p.pontos)
                    
                    if idx not in mapa_fada:
                        mapa_fada[idx] = {'nota_maxima': 10.0, 'motivos': []}
                    
                    mapa_fada[idx]['nota_maxima'] -= desconto
                    mapa_fada[idx]['motivos'].append(f"{regra.descricao} (-{desconto})")

            # 5. RESULTADO
            print("DADOS QUE O FRONTEND RECEBERIA PARA BLOQUEAR O FORMULÁRIO:")
            criterios = AvaliacaoService.CRITERIOS_FADA
            
            for i, nome_criterio in enumerate(criterios):
                dados = mapa_fada.get(i)
                if dados:
                    print(f"\n[BLOQUEIO] Atributo: {nome_criterio}")
                    print(f"   Nota Máxima Permitida: {dados['nota_maxima']}")
                    print(f"   Motivos: {', '.join(dados['motivos'])}")

            print("\n" + "-" * 60)
            db.session.rollback()

        except Exception as e:
            print(f"ERRO DE EXECUÇÃO: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()

if __name__ == "__main__":
    simular_preparacao_formulario()