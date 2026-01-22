import sys
import os

# Adiciona o diretório atual ao path para garantir importação correta
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
from backend.models.disciplina_turma import DisciplinaTurma
from backend.models.disciplina import Disciplina
from backend.models.turma import Turma
from backend.models.instrutor import Instrutor
from sqlalchemy.orm import joinedload

app = create_app()

def diagnosticar():
    with app.app_context():
        print("\n" + "=" * 80)
        print("🕵️  DIAGNÓSTICO DE VÍNCULOS FANTASMAS")
        print("=" * 80)
        print("Verificando discrepâncias entre o nome da Turma real e o nome gravado no Vínculo...\n")

        # Busca todos os vínculos carregando as relações necessárias
        # Joinedload otimiza para não fazer centenas de queries
        vinculos = db.session.query(DisciplinaTurma).options(
            joinedload(DisciplinaTurma.disciplina).joinedload(Disciplina.turma),
            joinedload(DisciplinaTurma.instrutor_1).joinedload(Instrutor.user),
            joinedload(DisciplinaTurma.instrutor_2).joinedload(Instrutor.user)
        ).all()

        fantasmas = []
        orfaos = []
        turmas_afetadas = set()

        for v in vinculos:
            # 1. Validação de Integridade (Vínculo quebrado no banco)
            if not v.disciplina:
                orfaos.append(f"Vínculo ID {v.id}: Aponta para Disciplina {v.disciplina_id} (Não existe)")
                continue
            
            if not v.disciplina.turma:
                orfaos.append(f"Vínculo ID {v.id}: Disciplina '{v.disciplina.materia}' não tem Turma associada")
                continue

            # 2. Validação de "Fantasma" (Divergência de String)
            turma_real = v.disciplina.turma
            nome_real = turma_real.nome.strip()
            nome_gravado = (v.pelotao or "").strip()

            # Se o nome gravado no vínculo for diferente do nome da turma atual
            if nome_real != nome_gravado:
                # Dados para o relatório
                instrutor1 = v.instrutor_1.user.nome_de_guerra if (v.instrutor_1 and v.instrutor_1.user) else "Nenhum"
                instrutor2 = v.instrutor_2.user.nome_de_guerra if (v.instrutor_2 and v.instrutor_2.user) else "Nenhum"
                
                fantasmas.append({
                    "id": v.id,
                    "disciplina": v.disciplina.materia,
                    "turma_real": nome_real,
                    "nome_antigo_gravado": nome_gravado,
                    "instrutores": f"{instrutor1} / {instrutor2}"
                })
                turmas_afetadas.add(nome_real)

        # --- RELATÓRIO ---

        if orfaos:
            print(f"❌ ERROS DE INTEGRIDADE (ÓRFÃOS): {len(orfaos)}")
            for o in orfaos:
                print(f"   - {o}")
            print("-" * 80)

        if fantasmas:
            print(f"👻 VÍNCULOS FANTASMAS ENCONTRADOS: {len(fantasmas)}")
            print(f"   (Existem no banco, mas 'invisíveis' devido a nomes antigos)\n")
            
            # Agrupar por Turma para facilitar leitura
            for turma_nome in sorted(list(turmas_afetadas)):
                print(f"📂 TURMA REAL: {turma_nome}")
                fantasmas_turma = [f for f in fantasmas if f['turma_real'] == turma_nome]
                
                for item in fantasmas_turma:
                    print(f"   🔴 Vínculo ID: {item['id']} | Matéria: {item['disciplina']}")
                    print(f"      Nome 'Cacheado' incorreto: '{item['nome_antigo_gravado']}'")
                    print(f"      Instrutores vinculados: {item['instrutores']}")
                    print("      ---")
                print("")
        else:
            print("✅ Nenhum vínculo fantasma detectado. Todos os nomes coincidem.")

        print("=" * 80)
        if fantasmas:
            print("💡 SOLUÇÃO: O Controller que enviei anteriormente corrige a LEITURA desses dados")
            print("   ignorando o nome incorreto. Para corrigir o BANCO definitivamente,")
            print("   podemos rodar um script que copie 'Turma.nome' para 'DisciplinaTurma.pelotao'.")

if __name__ == "__main__":
    diagnosticar()