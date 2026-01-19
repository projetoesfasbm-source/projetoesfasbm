import sys
import os
from datetime import datetime, timedelta
from sqlalchemy import text

# 1. Configuração do Ambiente para carregar Models e Services
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
from backend.models.aluno import Aluno
from backend.models.user import User
from backend.models.turma import Turma
from backend.models.processo_disciplina import ProcessoDisciplina, StatusProcesso
from backend.models.fada_avaliacao import FadaAvaliacao
from backend.services.justica_service import JusticaService

app = create_app()

def executar_teste_integracao():
    print("\n" + "="*70)
    print(">>> VALIDAÇÃO JURÍDICO-MATEMÁTICA CBFPM (INTEGRAÇÃO TOTAL) <<<")
    print("="*70)

    with app.app_context():
        try:
            # --- 1. SETUP DA TURMA E DATAS ---
            # Buscamos uma turma real ou criamos a de teste com datas válidas
            turma = Turma.query.filter(Turma.nome.like('%TURMA_TESTE_QA%')).first()
            if not turma:
                # Definindo datas para que o 2º ciclo já tenha começado e a formatura seja futura
                inicio_2_ciclo = datetime.now() - timedelta(days=10)
                data_formatura = datetime.now() + timedelta(days=100)
                
                turma = Turma(
                    nome="TURMA_TESTE_QA", 
                    school_id=1, 
                    ano=2026,
                    data_inicio_segundo_ciclo=inicio_2_ciclo,
                    data_formatura=data_formatura
                )
                db.session.add(turma)
                db.session.commit()
            
            # Cálculo da data válida para o fato (Ex: 5 dias após início do 2º ciclo)
            # Isso garante que a infração seja contabilizada pelo JusticaService
            data_fato_valida = turma.data_inicio_segundo_ciclo + timedelta(days=5)
            
            print(f"[Info] Janela de Avaliação:")
            print(f"      Início 2º Ciclo: {turma.data_inicio_segundo_ciclo.strftime('%d/%m/%Y')}")
            print(f"      Data do Fato:    {data_fato_valida.strftime('%d/%m/%Y')} (VÁLIDA)")
            print(f"      Limite (-40d):   {(turma.data_formatura - timedelta(days=40)).strftime('%d/%m/%Y')}")

            # --- 2. SETUP DO ALUNO ---
            user_teste = User.query.filter_by(matricula="999999_QA").first()
            if not user_teste:
                user_teste = User(matricula="999999_QA", nome_completo="SD TESTE QA", role="admin", password_hash="123")
                db.session.add(user_teste)
                db.session.commit()

            aluno_teste = Aluno.query.filter_by(user_id=user_teste.id).first()
            if not aluno_teste:
                aluno_teste = Aluno(user_id=user_teste.id, turma_id=turma.id, num_aluno=99, opm="EsFES/PoA")
                db.session.add(aluno_teste)
                db.session.commit()

            # --- 3. LIMPEZA DE REGISTROS ANTERIORES ---
            db.session.execute(text(f"DELETE FROM processos_disciplina WHERE aluno_id = {aluno_teste.id}"))
            db.session.execute(text(f"DELETE FROM fada_avaliacoes WHERE aluno_id = {aluno_teste.id}"))
            db.session.commit()

            # --- 4. INJEÇÃO DO GOLDEN SAMPLE (DADOS REAIS) ---
            print("\n[Passo 2] Injetando Infrações dentro da janela permitida...")
            
            # Infrações A e B: Afetam NDisc (Base 20)
            p1 = ProcessoDisciplina(
                aluno_id=aluno_teste.id, relator_id=user_teste.id, codigo_infracao="A", 
                fato_constatado="Falta Média A", status=StatusProcesso.FINALIZADO, 
                pontos=0.50, origem_punicao="NPCCAL", data_ocorrencia=data_fato_valida
            )
            p2 = ProcessoDisciplina(
                aluno_id=aluno_teste.id, relator_id=user_teste.id, codigo_infracao="B", 
                fato_constatado="Falta Média B", status=StatusProcesso.FINALIZADO, 
                pontos=0.50, origem_punicao="NPCCAL", data_ocorrencia=data_fato_valida
            )
            # Infração C: Crime (Afeta apenas FADA no cenário de teste)
            p3 = ProcessoDisciplina(
                aluno_id=aluno_teste.id, relator_id=user_teste.id, codigo_infracao="C", 
                fato_constatado="Crime C", status=StatusProcesso.FINALIZADO, 
                pontos=0.00, is_crime=True, origem_punicao="JUSTICA_COMUM", data_ocorrencia=data_fato_valida
            )
            db.session.add_all([p1, p2, p3])
            db.session.commit()

            # Injeção FADA (SQL Direto para garantir preenchimento de avaliador_id)
            print("[Passo 3] Injetando FADA com descontos específicos por atributo...")
            sql_fada = text("""
                INSERT INTO fada_avaliacoes 
                (aluno_id, lancador_id, avaliador_id, status, etapa_atual, expressao, planejamento, perseveranca, 
                apresentacao, lealdade, tato, equilibrio, disciplina, responsabilidade, maturidade, assiduidade, 
                pontualidade, diccao, lideranca, relacionamento, etica, produtividade, eficiencia, media_final, data_avaliacao)
                VALUES 
                (:aid, :uid, :uid, 'RASCUNHO', 'RASCUNHO', 7.5, 7.5, 5.0, 
                8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 7.7777777777, NOW())
            """)
            db.session.execute(sql_fada, {"aid": aluno_teste.id, "uid": user_teste.id})
            db.session.commit()

            # --- 5. EXECUÇÃO DO ALGORITMO REAL ---
            print("\n[Cálculo] Acionando JusticaService.calcular_aat_final...")
            aat, ndisc, fada_m = JusticaService.calcular_aat_final(aluno_teste.id)

            # --- 6. RELATÓRIO DE CONFORMIDADE ---
            # Conversão segura de tipos para evitar NoneType ou Decimal errors
            v_ndisc = float(ndisc) if ndisc is not None else 0.0
            v_fada = float(fada_m) if fada_m is not None else 0.0
            v_aat = float(aat) if aat is not None else 0.0

            # Verificadores Jurídicos
            check_ndisc = abs(v_ndisc - 9.50) < 0.01
            check_fada = abs(v_fada - 7.77) < 0.02
            check_aat = abs(v_aat - 8.64) < 0.02

            print("\n" + "-"*60)
            print(f"{'MÉTRICA':<20} | {'ESPERADO':<10} | {'OBTIDO':<10} | {'STATUS'}")
            print("-" * 60)
            print(f"{'Nota NDisc (Base 20)':<20} | {'9.50':<10} | {v_ndisc:<10.2f} | {'✅ OK' if check_ndisc else '❌ ERRO'}")
            print(f"{'Média FADA (Base 8)':<20} | {'7.77':<10} | {v_fada:<10.2f} | {'✅ OK' if check_fada else '❌ ERRO'}")
            print(f"{'Nota Final AAt':<20} | {'8.64':<10} | {v_aat:<10.2f} | {'✅ OK' if check_aat else '❌ ERRO'}")
            print("-" * 60)

            if check_ndisc and check_fada and check_aat:
                print("\n>>> RESULTADO FINAL: SUCESSO! O ALGORITMO ESTÁ INTEGRADO E CORRETO. <<<")
            else:
                print("\n>>> RESULTADO FINAL: FALHA! DIVERGÊNCIA NAS REGRAS DE NEGÓCIO. <<<")

        except Exception as e:
            print(f"\n[ERRO CRÍTICO] Falha no teste: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Limpeza opcional: Comente as linhas abaixo se quiser ver os dados no banco após o teste
            if 'aluno_teste' in locals() and aluno_teste:
                db.session.execute(text(f"DELETE FROM processos_disciplina WHERE aluno_id = {aluno_teste.id}"))
                db.session.execute(text(f"DELETE FROM fada_avaliacoes WHERE aluno_id = {aluno_teste.id}"))
                db.session.delete(aluno_teste)
                db.session.delete(user_teste)
                db.session.commit()
                print("\n[Limpeza] Ambiente restaurado.")

if __name__ == "__main__":
    executar_teste_integracao()