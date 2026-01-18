import sys
import os
from datetime import date, datetime, timedelta

sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
from backend.models.school import School
from backend.models.turma import Turma
from backend.models.aluno import Aluno
from backend.models.ciclo import Ciclo
from backend.models.processo_disciplina import ProcessoDisciplina, StatusProcesso
from backend.models.elogio import Elogio
from backend.models.user import User
from backend.services.justica_service import JusticaService

app = create_app()

def teste_completo_avaliacao():
    with app.app_context():
        print("\n" + "="*60)
        print("⚡ TESTE: ELOGIOS E FÓRMULA FINAL (AAt = (NDisc+FADA)/2)")
        print("="*60)

        try:
            # 1. SETUP
            school = School(nome="Escola Formula Teste", npccal_type="cspm")
            db.session.add(school)
            db.session.flush()

            hoje = date.today()
            dt_inicio_2_ciclo = hoje - timedelta(days=50)
            dt_formatura = hoje + timedelta(days=100)
            
            ciclo2 = Ciclo(school_id=school.id, nome="2º Ciclo", data_inicio=dt_inicio_2_ciclo)
            db.session.add(ciclo2)
            
            turma = Turma(nome="Turma Formula", ano="2026", school_id=school.id)
            turma.data_formatura = dt_formatura
            db.session.add(turma)
            db.session.flush()

            user = User(matricula="12345", nome_completo="Aluno Formula", nome_de_guerra="Formula", role="aluno")
            db.session.add(user)
            db.session.flush()
            
            aluno = Aluno(user_id=user.id, turma_id=turma.id, opm="ESFAS")
            db.session.add(aluno)
            db.session.flush()

            # 2. INSERINDO DADOS
            # A) Uma punição MÉDIA (-0.5 pts)
            punicao = ProcessoDisciplina(
                aluno_id=aluno.id, relator_id=user.id, status=StatusProcesso.FINALIZADO,
                data_ocorrencia=hoje, data_decisao=hoje,
                pontos=0.5, is_crime=False, origem_punicao="NPCCAL", fato_constatado="Falta Média"
            )
            db.session.add(punicao)

            # B) Dois Elogios (+0.5 cada = +1.0)
            # CORREÇÃO: Criando sem argumentos extras e definindo atributos manualmente
            # para evitar erro de __init__ e erro de coluna nula.
            elo1 = Elogio()
            elo1.aluno_id = aluno.id
            elo1.registrado_por_id = user.id # Campo direto do banco (contorna erro autor_id)
            elo1.data_elogio = hoje
            elo1.descricao = "Bom serviço"
            elo1.pontos = 0.0 # Pontos do elogio em si (se houver regra antiga), mas FADA conta qtd.
            
            elo2 = Elogio()
            elo2.aluno_id = aluno.id
            elo2.registrado_por_id = user.id
            elo2.data_elogio = hoje
            elo2.descricao = "Boa conduta"
            elo2.pontos = 0.0

            db.session.add_all([elo1, elo2])
            db.session.flush()

            # 3. CÁLCULO ESPERADO
            # NDisc: Base 20 - 0.5 = 19.5 / 2 = 9.75
            # FADA: Base 8.0 - 0.5 + 1.0 (2 elogios) = 8.5
            
            print("\n>> Executando Cálculos...")
            aat, ndisc, fada = JusticaService.calcular_aat_final(aluno.id)

            print(f"   NDisc Calculada: {ndisc} (Esperado: 9.75)")
            print(f"   FADA Calculada:  {fada}  (Esperado: 8.5)")
            
            if ndisc == 9.75 and fada == 8.5:
                print("\n✅ SUCESSO ABSOLUTO.")
            else:
                print("\n❌ ERRO NOS CÁLCULOS.")

        except Exception as e:
            print(f"ERRO: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.session.rollback()

if __name__ == "__main__":
    teste_completo_avaliacao()