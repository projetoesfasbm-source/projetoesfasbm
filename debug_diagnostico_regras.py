import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
from backend.models.user import User # Import necessário
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
        
        try:
            # 1. SETUP
            escola = School(nome="Escola Teste CBFPM", npccal_type="cbfpm")
            db.session.add(escola)
            db.session.flush()

            ciclo1 = Ciclo(school_id=escola.id, nome="1º Módulo", data_inicio=datetime.now() - timedelta(days=60), data_fim=datetime.now() - timedelta(days=30))
            ciclo2 = Ciclo(school_id=escola.id, nome="2º Módulo", data_inicio=datetime.now() - timedelta(days=29), data_fim=datetime.now() + timedelta(days=30))
            db.session.add_all([ciclo1, ciclo2])
            db.session.flush()

            turma = Turma(nome="Pelotão Alfa", ano="2026", school_id=escola.id)
            db.session.add(turma)
            db.session.flush()
            
            # CORREÇÃO: Criar Usuário e depois Aluno
            user = User(
                matricula="888888",
                nome_completo="Aluno Teste Regra", 
                nome_de_guerra="Teste",
                role="aluno"
            )
            db.session.add(user)
            db.session.flush()

            aluno = Aluno(
                user_id=user.id,
                opm="ESFAS",
                turma_id=turma.id
            )
            db.session.add(aluno)
            db.session.flush()

            # 2. CENÁRIO DE INFRAÇÃO
            regra = DisciplineRule(
                npccal_type="cbfpm",
                codigo="001",
                descricao="Chegar atrasado",
                pontos=0.5,
                atributo_fada_id=12
            )
            db.session.add(regra)
            db.session.flush()

            proc = ProcessoDisciplina(
                aluno_id=aluno.id,
                relator_id=user.id, # Precisa de um relator (usando o próprio para teste)
                regra_id=regra.id,
                pontos=0.5,
                status=StatusProcesso.FINALIZADO,
                data_ocorrencia=datetime.now(),
                data_decisao=datetime.now(),
                origem_punicao="NPCCAL",
                fato_constatado="Teste"
            )
            db.session.add(proc)
            db.session.flush()

            print(f"\n[CENÁRIO]: Aluno {user.nome_de_guerra} (CBFPM).")
            print(f"[CENÁRIO]: Infração 'Média' (0.5 pts) cometida no 2º Ciclo.")

            # 3. VERIFICAÇÃO NDISC
            ndisc_calc = JusticaService.calcular_ndisc_aluno(aluno.id)
            print(f"\n--- ANÁLISE NDISC ---")
            print(f"NDisc Calculada: {ndisc_calc}")
            if ndisc_calc == 9.75:
                print("✅ NDisc correta.")
            else:
                print(f"❌ ERRO NDisc: Esperado 9.75, recebeu {ndisc_calc}.")

            # 4. VERIFICAÇÃO FADA ESTIMADA
            fada_est = JusticaService.calcular_fada_estimada(aluno.id)
            print(f"\n--- ANÁLISE FADA (Estimada/Global) ---")
            print(f"FADA Estimada: {fada_est}")

            # 5. O GRANDE TESTE: AVALIAÇÃO FINAL
            dados_formulario = {
                'aluno_id': aluno.id,
                'periodo_inicio': (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d'),
                'periodo_fim': datetime.now().strftime('%Y-%m-%d'),
                'observacoes': 'Teste'
            }
            # Preenche critério 0 a 17 com nota 10.0
            for i in range(18):
                dados_formulario[f'criterio_{i}'] = 10.0
            
            # Usando ID 1 (Assumindo Admin) ou o próprio user para teste
            AvaliacaoService.criar_avaliacao(dados_formulario, avaliador_id=user.id)
            
            avaliacao = AvaliacaoService.get_avaliacoes_aluno(aluno.id)[0]
            
            print(f"\n--- ANÁLISE AVALIAÇÃO FINAL (Onde mora o perigo) ---")
            print(f"Nota FADA Final (Baseada no Input Manual): {avaliacao.nota_fada}")
            
            if avaliacao.nota_fada == 10.0:
                print("⚠️  ALERTA CRÍTICO: O sistema aceitou nota 10.0 na FADA mesmo com infração registrada.")
            else:
                print("✅ O sistema aplicou desconto automaticamente.")

            db.session.rollback()

        except Exception as e:
            print(f"ERRO DE EXECUÇÃO: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()

if __name__ == "__main__":
    diagnostico_sistema()