import sys
import os
import uuid
import random
from datetime import datetime, timedelta

# Garante que o Python encontre os módulos do projeto
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
from backend.models.aluno import Aluno
from backend.models.user import User
from backend.models.turma import Turma
from backend.models.processo_disciplina import ProcessoDisciplina, StatusProcesso
from backend.services.justica_service import JusticaService

app = create_app()

def executar_teste_golden_sample():
    print("\n" + "="*60)
    print(">>> INICIANDO VALIDAÇÃO DO ALGORITMO (GOLDEN SAMPLE) <<<")
    print("="*60)

    with app.app_context():
        try:
            # 1. SETUP: CRIAR AMBIENTE TEMPORÁRIO (DADOS ÚNICOS)
            print("\n[1] Criando Turma e Aluno Temporários...")
            
            # Gera identificadores únicos para evitar colisão no banco
            suffix = str(uuid.uuid4())[:8]
            matr_aluno = f"TEST_AL_{suffix}"
            matr_admin = f"TEST_AD_{suffix}"
            
            # Turma com datas válidas
            turma_teste = Turma(
                nome=f"TURMA_QA_{suffix}", 
                school_id=1, 
                ano=2026,
                data_formatura=datetime.now() + timedelta(days=100)
            )
            db.session.add(turma_teste)
            db.session.flush()

            # Usuário Aluno
            user_aluno = User(
                matricula=matr_aluno, 
                nome_completo="ALUNO TESTE MATEMATICO", 
                role="aluno", 
                password_hash="teste"
            )
            db.session.add(user_aluno)
            db.session.flush()

            # Perfil Aluno
            aluno = Aluno(
                user_id=user_aluno.id, 
                turma_id=turma_teste.id, 
                num_aluno=99,
                opm="EsFES/PoA" 
            )
            db.session.add(aluno)
            db.session.flush()

            # Usuário Relator (Admin)
            user_admin = User(
                matricula=matr_admin, 
                nome_completo="ADMIN TESTE", 
                role="admin", 
                password_hash="teste"
            )
            db.session.add(user_admin)
            db.session.flush()

            # 2. CENÁRIO: INJETAR INFRAÇÕES DO GOLDEN SAMPLE
            print("[2] Injetando Infrações do Cenário...")
            
            data_fato = datetime.now() - timedelta(days=1)

            # Infração A: Falta Média (-0.50) -> Afeta NDisc
            p1 = ProcessoDisciplina(
                aluno_id=aluno.id, relator_id=user_admin.id,
                codigo_infracao="A", fato_constatado="Falta Média A",
                status=StatusProcesso.FINALIZADO, pontos=0.50,
                origem_punicao="NPCCAL", data_ocorrencia=data_fato, is_crime=False
            )

            # Infração B: Falta Média (-0.50) -> Afeta NDisc
            p2 = ProcessoDisciplina(
                aluno_id=aluno.id, relator_id=user_admin.id,
                codigo_infracao="B", fato_constatado="Falta Média B",
                status=StatusProcesso.FINALIZADO, pontos=0.50,
                origem_punicao="NPCCAL", data_ocorrencia=data_fato, is_crime=False
            )

            # Infração C: Crime (-3.00) -> NÃO afeta NDisc, afeta FADA (Ética)
            p3 = ProcessoDisciplina(
                aluno_id=aluno.id, relator_id=user_admin.id,
                codigo_infracao="C", fato_constatado="Crime Comum",
                status=StatusProcesso.FINALIZADO, pontos=0.00, 
                origem_punicao="JUSTICA_COMUM", data_ocorrencia=data_fato, is_crime=True 
            )

            db.session.add_all([p1, p2, p3])
            db.session.flush()

            # --- MOCKS PARA TESTE LÓGICO ---
            # Força o sistema a acreditar que as datas são válidas
            JusticaService.verificar_elegibilidade_punicao = lambda p, i, l: True
            # Força o sistema a acreditar que é um curso pontuado (CBFPM/CSPM)
            JusticaService._is_curso_pontuado = lambda *args, **kwargs: True

            # 3. TESTE NDISC
            print("\n[3] Validando Cálculo NDisc...")
            # Esperado: 20 - 0.5 - 0.5 = 19.0. Média = 19/2 = 9.50
            ndisc_obtido = JusticaService.calcular_ndisc_aluno(aluno.id)
            print(f"    > Esperado: 9.50 | Obtido: {ndisc_obtido}")
            
            if abs(ndisc_obtido - 9.50) > 0.01:
                raise AssertionError(f"Erro NDisc: Esperado 9.50, recebeu {ndisc_obtido}")

            # 4. TESTE FADA ESTIMADA (Cálculo Automático)
            print("\n[4] Validando FADA Estimada (Automática)...")
            # Esperado:
            # Base Total = 18 * 8.0 = 144.0
            # Descontos = 0.5 (A) + 0.5 (B) + 3.0 (C) = 4.0
            # Massa Final = 140.0
            # Média = 140 / 18 = 7.7777...
            fada_estimada = JusticaService.calcular_fada_estimada(aluno.id)
            print(f"    > Esperado: 7.7777 | Obtido: {fada_estimada:.4f}")
            
            if abs(fada_estimada - 7.7777) > 0.001:
                raise AssertionError(f"Erro FADA: Esperado 7.7777, recebeu {fada_estimada}")

            # 5. TESTE TRAVA DE SEGURANÇA (LIMITES MANUAIS)
            print("\n[5] Validando Trava de Limites por Atributo...")
            # Simula vínculo manual feito pelo Admin
            mapa_vinculos = {
                str(p1.id): 1, # A (0.5) -> Atributo 1
                str(p2.id): 2, # B (0.5) -> Atributo 2
                str(p3.id): 3  # C (3.0) -> Atributo 3
            }
            
            limites, erro = JusticaService.calcular_limites_fada(aluno.id, mapa_vinculos)
            
            if erro:
                print(f"    [ERRO CRÍTICO] Falha na validação de vínculos: {erro}")
            else:
                # Validação Atributo 1 (Teto deve ser 10.0 - 0.5 = 9.5)
                print(f"    > Atributo 1 (Falta Média): Teto Esperado 9.50 | Obtido: {limites[0]}")
                if limites[0] != 9.5: raise AssertionError(f"Erro Teto Attr 1: {limites[0]}")

                # Validação Atributo 3 (Crime -3.0) -> Teto deve ser 10.0 - 3.0 = 7.0
                print(f"    > Atributo 3 (Crime):       Teto Esperado 7.00 | Obtido: {limites[2]}")
                if limites[2] != 7.0: raise AssertionError(f"Erro Teto Attr 3: {limites[2]}")

                # Validação Atributo 4 (Limpo) -> Teto 10.0
                print(f"    > Atributo 4 (Limpo):       Teto Esperado 10.0 | Obtido: {limites[3]}")
                if limites[3] != 10.0: raise AssertionError(f"Erro Teto Attr 4: {limites[3]}")

            print("\n" + "="*60)
            print(">>> SUCESSO! TODOS OS TESTES MATEMÁTICOS PASSARAM <<<")
            print("="*60)

        except AssertionError as ae:
            print(f"\n[FALHA LÓGICA]: {ae}")
        except Exception as e:
            print(f"\n[ERRO DE EXECUÇÃO]: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print("\n[6] Limpando dados temporários (Rollback)...")
            db.session.rollback()

if __name__ == "__main__":
    executar_teste_golden_sample()