import sys
import os
import traceback
from sqlalchemy import inspect

# Adiciona o diretório atual ao path
sys.path.append(os.getcwd())

# --- BLOCO DE IMPORTAÇÃO ROBUSTO (IGUAL AO debug_justica.py) ---
app = None
try:
    # Tentativa 1: Factory no pacote backend
    from backend import create_app
    app = create_app()
    print(">> [SUCESSO] App inicializado via 'from backend import create_app'")
except ImportError:
    try:
        # Tentativa 2: Factory no módulo backend.app (A QUE FUNCIONOU ANTES)
        from backend.app import create_app
        app = create_app()
        print(">> [SUCESSO] App inicializado via 'from backend.app import create_app'")
    except ImportError:
        print(">> [AVISO] 'create_app' não encontrado. Tentando 'app' direto...")
        try:
            # Tentativa 3: Instância direta
            from backend.app import app
            print(">> [SUCESSO] App importado de 'backend.app'")
        except ImportError:
            print("\nERRO FATAL: Não consegui encontrar a instância do Flask (app).")
            sys.exit(1)

from backend.models.database import db
from backend.models.ciclo import Ciclo
from backend.models.disciplina_turma import DisciplinaTurma
from backend.models.horario import Horario

def diagnosticar():
    with app.app_context():
        print("="*50)
        print("DIAGNÓSTICO: VÍNCULOS, CICLOS E HORÁRIOS")
        print("="*50)

        # 1. VERIFICAR TABELA 'CICLOS'
        print("\n[1] Verificando estrutura da tabela 'ciclos'...")
        try:
            inspector = inspect(db.engine)
            cols = [c['name'] for c in inspector.get_columns('ciclos')]
            print(f"   Colunas encontradas: {cols}")
            
            novas = ['data_inicio', 'data_fim']
            faltantes = [c for c in novas if c not in cols]
            
            if faltantes:
                print(f"   [ERRO CRÍTICO] Colunas faltando em 'ciclos': {faltantes}")
                print("   SOLUÇÃO: Precisaremos rodar a migração para 'ciclos'.")
            else:
                print("   [OK] Tabela ciclos está atualizada.")
        except Exception as e:
            print(f"   [ERRO] Falha ao inspecionar ciclos: {e}")

        # 2. TESTE DE CONSULTA EM CICLOS
        print("\n[2] Testando consulta em Ciclos...")
        try:
            ciclos = db.session.query(Ciclo).limit(3).all()
            if not ciclos:
                print("   [AVISO] Nenhum ciclo encontrado no banco.")
            else:
                print(f"   Sucesso. {len(ciclos)} ciclos encontrados.")
                for c in ciclos:
                    # Usa getattr para não quebrar se a coluna não existir no objeto Python (embora deva existir)
                    dt_ini = getattr(c, 'data_inicio', 'N/A')
                    print(f"   - Ciclo ID {c.id}: {c.nome} | Inicio: {dt_ini}")
        except Exception as e:
            print("   [ERRO FATAL] Falha ao ler Ciclos. Provável coluna inexistente no banco.")
            print(f"   Detalhe: {str(e)}")

        # 3. TESTE DE VÍNCULOS (DisciplinaTurma)
        print("\n[3] Testando consulta de Vínculos (DisciplinaTurma)...")
        try:
            vinculos = db.session.query(DisciplinaTurma).limit(1).all()
            print(f"   Query Vínculos: OK (Retornou {len(vinculos)} registro(s))")
        except Exception as e:
            print("   [ERRO FATAL] Falha ao ler Vínculos:")
            print(str(e))

        # 4. TESTE DE HORÁRIO
        print("\n[4] Testando consulta de Horário...")
        try:
            horario = db.session.query(Horario).limit(1).all()
            print(f"   Query Horário: OK (Retornou {len(horario)} registro(s))")
        except Exception as e:
            print("   [ERRO FATAL] Falha ao ler Horários:")
            print(str(e))

if __name__ == "__main__":
    diagnosticar()