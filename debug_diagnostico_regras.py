import sys
import os
from datetime import datetime, timedelta

# Adiciona o diretório atual ao path para importar o backend
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
from backend.models.aluno import Aluno
from backend.models.turma import Turma
from backend.models.school import School
from backend.models.processo_disciplina import ProcessoDisciplina, StatusProcesso
from backend.models.discipline_rule import DisciplineRule
from backend.models.ciclo import Ciclo
from backend.services.justica_service import JusticaService
from backend.services.avaliacao_service import AvaliacaoService

app = create_app()

def diagnostico_sistema():
    with app.app_context():
        print("=== INICIANDO DIAGNÓSTICO CIRÚRGICO DE REGRAS ===")
        
        # 1. SETUP DO CENÁRIO (Simulação em Memória/Rollback)
        try:
            # Criar Escola CBFPM (Pontuada) - CORREÇÃO: 'nome' em vez de 'name'
            escola = School(nome="Escola Teste CBFPM", npccal_type="cbfpm")
            db.session.add(escola)
            db.session.flush()

            # Criar Ciclos (Necessário para a regra do 2º Ciclo)
            # Ciclo 1: Passado / Ciclo 2: Atual (para as punições contarem)
            ciclo1 = Ciclo(school_id=escola.id, nome="1º Módulo", data_inicio=datetime.now() - timedelta(days=60), data_fim=datetime.now() - timedelta(days=30))
            ciclo2 = Ciclo(school_id=escola.id, nome="2º Módulo", data_inicio=datetime.now() - timedelta(days=29), data_fim=datetime.now() + timedelta(days=30))
            db.session.add_all([ciclo1, ciclo2])
            db.session.flush()

            # Criar Turma e Aluno - CORREÇÃO: 'nome' em vez de 'name'
            turma = Turma(nome="Pelotão Alfa", school_id=escola.id)
            db.session.add(turma)
            db.session.flush()
            
            aluno = Aluno(nome_completo="Aluno Teste Regra", nome_guerra="Teste", turma_id=turma.id)
            db.session.add(aluno)
            db.session.flush()

            # 2. CENÁRIO DE INFRAÇÃO
            # Vamos criar uma regra que afeta o Atributo 12 (Pontualidade) na FADA
            # E gera 0.5 pontos na NDisc
            regra = DisciplineRule(
                npccal_type="cbfpm",
                codigo="001",
                descricao="Chegar atrasado",
                pontos=0.5, # Média
                atributo_fada_id=12 # Supondo que 12 seja Pontualidade
            )
            db.session.add(regra)
            db.session.flush()

            # Criar Processo Finalizado DENTRO do 2º Ciclo
            proc = ProcessoDisciplina(
                aluno_id=aluno.id,
                regra_id=regra.id,
                pontos=0.5,
                status=StatusProcesso.FINALIZADO,
                data_ocorrencia=datetime.now(), # Hoje (dentro do ciclo 2)
                data_decisao=datetime.now(),
                origem_punicao="NPCCAL"
            )
            db.session.add(proc)
            db.session.flush()

            print(f"\n[CENÁRIO]: Aluno {aluno.nome_guerra} (CBFPM).")
            print(f"[CENÁRIO]: Infração 'Média' (0.5 pts) cometida no 2º Ciclo.")
            print(f"[CENÁRIO]: Regra vinculada ao Atributo FADA ID {regra.atributo_fada_id}.")

            # 3. VERIFICAÇÃO NDISC (JusticaService)
            ndisc_calc = JusticaService.calcular_ndisc_aluno(aluno.id)
            # Esperado: (20 - 0.5) / 2 = 9.75
            print(f"\n--- ANÁLISE NDISC ---")
            print(f"NDisc Calculada: {ndisc_calc}")
            if ndisc_calc == 9.75:
                print("✅ NDisc correta (Fórmula base 20 funcionando).")
            else:
                print(f"❌ ERRO NDisc: Esperado 9.75, recebeu {ndisc_calc}.")

            # 4. VERIFICAÇÃO FADA ESTIMADA (JusticaService)
            # O serviço atual faz uma estimativa global baseada na gravidade
            fada_est = JusticaService.calcular_fada_estimada(aluno.id)
            # Esperado (Regra atual): Base 8.0 - 0.50 (Falta Média) = 7.5
            print(f"\n--- ANÁLISE FADA (Estimada/Global) ---")
            print(f"FADA Estimada: {fada_est}")
            if fada_est == 7.5:
                print("✅ FADA Global calculando descontos genéricos corretamente.")
            else:
                print(f"❌ ERRO FADA Global: Esperado 7.5, recebeu {fada_est}.")

            # 5. O GRANDE TESTE: AVALIAÇÃO FINAL (AvaliacaoService)
            # Vamos simular o envio do formulário manual SEM aplicar o desconto manualmente
            # Se o sistema não forçar, a nota ficará errada.
            
            # Simulando envio de notas 10.0 para todos os critérios
            dados_formulario = {
                'aluno_id': aluno.id,
                'periodo_inicio': (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d'),
                'periodo_fim': datetime.now().strftime('%Y-%m-%d'),
                'observacoes': 'Teste'
            }
            # Preenche critério 0 a 17 com nota 10.0
            for i in range(18):
                dados_formulario[f'criterio_{i}'] = 10.0
            
            # Aqui está o ponto cego: O usuário manda 10.0 em tudo. 
            # O sistema DEVERIA identificar que o critério 12 tem uma infração e baixar a nota.
            AvaliacaoService.criar_avaliacao(dados_formulario, avaliador_id=1) # Mock User ID 1
            
            avaliacao = AvaliacaoService.get_avaliacoes_aluno(aluno.id)[0]
            
            print(f"\n--- ANÁLISE AVALIAÇÃO FINAL (Onde mora o perigo) ---")
            print(f"Nota FADA Final (Baseada no Input Manual): {avaliacao.nota_fada}")
            
            # Se a nota for 10.0, o sistema falhou em aplicar a regra do Art 125 §8º
            if avaliacao.nota_fada == 10.0:
                print("⚠️  ALERTA CRÍTICO: O sistema aceitou nota 10.0 na FADA mesmo com infração registrada.")
                print("    Isso confirma que o desconto no atributo específico NÃO é automático.")
                print("    Necessário alterar 'AvaliacaoService.criar_avaliacao' ou o Frontend.")
            else:
                print("✅ O sistema aplicou desconto automaticamente.")

            # Rollback para não sujar o banco
            db.session.rollback()
            print("\nDiagnóstico concluído. Banco de dados preservado (Rollback).")

        except Exception as e:
            print(f"ERRO DE EXECUÇÃO: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()

if __name__ == "__main__":
    diagnostico_sistema()