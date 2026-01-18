import sys
import os
from datetime import date, datetime, timedelta

# Ajuste de path para rodar na raiz do projeto
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
from backend.models.school import School
from backend.models.turma import Turma
from backend.models.aluno import Aluno
from backend.models.ciclo import Ciclo
from backend.models.processo_disciplina import ProcessoDisciplina, StatusProcesso
from backend.models.user import User
from backend.services.justica_service import JusticaService

app = create_app()

def teste_validacao_final():
    with app.app_context():
        print("\n" + "="*60)
        print("⚡ INICIANDO VALIDAÇÃO FINAL DE REGRAS (INTEGRAÇÃO)")
        print("="*60)

        try:
            # 1. SETUP DE CENÁRIO (Escola, Turma, Ciclos)
            print("\n>> 1. Criando Cenário Mock (Escola CBFPM)...")
            
            # Escola Pontuada (CORREÇÃO: 'nome' em vez de 'name')
            school = School(nome="Escola Teste Regras", npccal_type="cbfpm")
            db.session.add(school)
            db.session.flush()

            # Datas Críticas
            hoje = date.today()
            data_formatura = hoje + timedelta(days=50) # Formatura daqui a 50 dias
            limite_40_dias = data_formatura - timedelta(days=40) # Limite é daqui a 10 dias
            
            # Ciclos: Ciclo 1 (Passado) e Ciclo 2 (Começou há 20 dias)
            c1_inicio = hoje - timedelta(days=120)
            c2_inicio = hoje - timedelta(days=20) # Ciclo 2 começou 20 dias atrás
            
            ciclo1 = Ciclo(school_id=school.id, nome="1º Módulo Básico", data_inicio=c1_inicio, data_fim=c2_inicio - timedelta(days=1))
            ciclo2 = Ciclo(school_id=school.id, nome="2º Módulo Específico", data_inicio=c2_inicio, data_fim=data_formatura)
            db.session.add_all([ciclo1, ciclo2])
            db.session.flush()

            # Turma com Data de Formatura
            turma = Turma(nome="Turma Validação", ano="2026", school_id=school.id)
            turma.data_formatura = data_formatura # <--- O CAMPO NOVO
            db.session.add(turma)
            db.session.flush()

            # Aluno e Usuário
            user = User(matricula="999000", nome_completo="Aluno Teste", nome_de_guerra="Teste", role="aluno")
            db.session.add(user)
            db.session.flush()
            
            # Aluno vinculado à turma
            aluno = Aluno(user_id=user.id, turma_id=turma.id, opm="ESFAS")
            db.session.add(aluno)
            db.session.flush()

            print(f"   [INFO] Início 2º Ciclo: {c2_inicio}")
            print(f"   [INFO] Data Formatura: {data_formatura}")
            print(f"   [INFO] Limite Atitudinal (40d): {limite_40_dias}")

            # 2. TESTES DE CASO (Criação de Processos)
            
            # CASO A: Infração NPCCAL ANTES do 2º Ciclo (Deve ser ignorada)
            # Data: 30 dias atrás (Ciclo 2 começou há 20 dias)
            data_caso_a = hoje - timedelta(days=30)
            p_a = ProcessoDisciplina(
                aluno_id=aluno.id, relator_id=user.id, status=StatusProcesso.FINALIZADO,
                data_ocorrencia=data_caso_a, data_decisao=data_caso_a,
                pontos=1.0, is_crime=False, origem_punicao="NPCCAL", fato_constatado="Falta Antiga"
            )
            
            # CASO B: Infração NPCCAL VÁLIDA (Dentro do 2º Ciclo e antes dos 40 dias finais)
            # Data: Ontem (Dentro do prazo)
            data_caso_b = hoje - timedelta(days=1)
            p_b = ProcessoDisciplina(
                aluno_id=aluno.id, relator_id=user.id, status=StatusProcesso.FINALIZADO,
                data_ocorrencia=data_caso_b, data_decisao=data_caso_b,
                pontos=0.5, is_crime=False, origem_punicao="NPCCAL", fato_constatado="Falta Válida"
            )

            # CASO C: Infração NPCCAL DEPOIS do Limite (40 dias finais)
            # Data: Daqui a 15 dias (Limite é daqui a 10 dias)
            data_caso_c = hoje + timedelta(days=15)
            p_c = ProcessoDisciplina(
                aluno_id=aluno.id, relator_id=user.id, status=StatusProcesso.FINALIZADO,
                data_ocorrencia=data_caso_c, data_decisao=data_caso_c,
                pontos=2.0, is_crime=False, origem_punicao="NPCCAL", fato_constatado="Falta Tardia"
            )

            # CASO D: CRIME ANTES do 2º Ciclo (Deve contar pois Crime conta sempre)
            # Data: 30 dias atrás (Igual ao caso A, mas é Crime)
            data_caso_d = hoje - timedelta(days=30)
            p_d = ProcessoDisciplina(
                aluno_id=aluno.id, relator_id=user.id, status=StatusProcesso.FINALIZADO,
                data_ocorrencia=data_caso_d, data_decisao=data_caso_d,
                pontos=0.0, is_crime=True, origem_punicao="NPCCAL", fato_constatado="Crime Antigo"
                # Nota: JusticaService define os pontos do crime na hora do calculo (3.0)
            )

            db.session.add_all([p_a, p_b, p_c, p_d])
            db.session.flush()

            # 3. VERIFICAÇÃO DOS CÁLCULOS
            print("\n>> 2. Executando Cálculos do Service...")
            
            # A) NDisc
            
            fada_calc = JusticaService.calcular_fada_estimada(aluno.id)
            
            print(f"\n   [RESULTADO] Nota FADA Calculada: {fada_calc}")
            
            # Cálculo Esperado na Mão:
            # Base: 8.0
            # Descontos:
            # - p_a (Falta Grave): Ignorado (Antes 2º ciclo) -> 0.0
            # - p_b (Falta Média): Contabilizado -> -0.50
            # - p_c (Falta Gravíssima): Ignorado (Regra 40 dias) -> 0.0
            # - p_d (Crime): Contabilizado (Crime conta sempre) -> -3.00
            #
            # Total Esperado: 8.0 - 0.5 - 3.0 = 4.5
            
            if fada_calc == 4.5:
                print("   ✅ SUCESSO: A nota FADA é 4.5 exatos.")
                print("      - Atestou que falta antes do ciclo foi ignorada.")
                print("      - Atestou que falta nos 40 dias finais foi ignorada.")
                print("      - Atestou que Crime antigo foi contabilizado.")
                print("      - Atestou que falta válida foi contabilizada.")
            else:
                print(f"   ❌ ERRO: Esperado 4.5, recebeu {fada_calc}")
                
            # Teste NDisc rápido (apenas p_b deve contar 0.5)
            # Formula: (20 - pontos) / 2
            # Se p_d (crime) tem 0 pontos no registro, só p_b soma 0.5.
            # Esperado: (20 - 0.5) / 2 = 9.75
            ndisc_calc = JusticaService.calcular_ndisc_aluno(aluno.id)
            if ndisc_calc == 9.75:
                print(f"   ✅ SUCESSO: NDisc calculada corretamente ({ndisc_calc}).")
            else:
                print(f"   ❌ ERRO NDisc: Esperado 9.75, recebeu {ndisc_calc}.")

        except Exception as e:
            print(f"\n❌ ERRO DE EXECUÇÃO: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print("\n" + "="*60)
            print("REVERTENDO ALTERAÇÕES NO BANCO (ROLLBACK)...")
            db.session.rollback()
            print("Banco de dados limpo.")
            print("="*60)

if __name__ == "__main__":
    teste_validacao_final()