import sys
import os
import traceback

# Adiciona o diretório atual ao path
sys.path.append(os.getcwd())

# --- 1. TENTATIVA DE IMPORTAÇÃO DA APP ---
app = None
try:
    # Padrão Factory (Mais comum e provável)
    from backend import create_app
    app = create_app()
    print(">> [SUCESSO] App inicializado via 'from backend import create_app'")
except ImportError:
    try:
        from backend.app import create_app
        app = create_app()
        print(">> [SUCESSO] App inicializado via 'from backend.app import create_app'")
    except ImportError:
        print(">> [AVISO] Não foi possível achar 'create_app'. Tentando importar 'app' direto...")
        try:
            from backend.app import app
            print(">> [SUCESSO] App importado de 'backend.app'")
        except ImportError:
            print("\nERRO FATAL: Não consegui encontrar a instância do Flask (app).")
            print("Liste o conteúdo de backend/app.py ou backend/__init__.py para verificar onde o 'app' é criado.")
            sys.exit(1)

# --- 2. IMPORTAÇÃO DO BANCO DE DADOS ---
try:
    from backend.models.database import db
    print(">> [SUCESSO] DB importado de 'backend.models.database'")
except ImportError:
    print("\nERRO FATAL: Não consegui importar 'db' de 'backend.models.database'.")
    sys.exit(1)

# --- 3. IMPORTS DOS MODELOS ---
from backend.models.processo_disciplina import ProcessoDisciplina
from backend.models.aluno import Aluno
from backend.models.turma import Turma
from sqlalchemy import select, inspect

def diagnosticar():
    with app.app_context():
        print("\n" + "="*40)
        print("INICIANDO DIAGNÓSTICO PROFUNDO")
        print("="*40)

        # CHECK 1: COLUNAS NO BANCO
        print("\n[1] Verificando colunas na tabela 'processos_disciplina'...")
        try:
            inspector = inspect(db.engine)
            columns = [c['name'] for c in inspector.get_columns('processos_disciplina')]
            print(f"   Colunas atuais: {columns}")
            
            novas = ['is_crime', 'tipo_sancao', 'dias_sancao', 'origem_punicao', 'status']
            faltantes = [c for c in novas if c not in columns]
            
            if faltantes:
                print(f"   [ERRO CRÍTICO] Falta aplicar a migração! Colunas ausentes: {faltantes}")
                print("   SOLUÇÃO: Rode 'flask db upgrade' no bash.")
            else:
                print("   [OK] Todas as colunas novas existem.")
        except Exception as e:
            print(f"   [ERRO] Falha ao inspecionar banco: {e}")

        # CHECK 2: TESTE DE DADOS E TIPOS
        print("\n[2] Verificando integridade dos dados (Status)...")
        try:
            # Pega os últimos 5 processos
            processos = db.session.query(ProcessoDisciplina).order_by(ProcessoDisciplina.id.desc()).limit(5).all()
            if not processos:
                print("   [AVISO] A tabela 'processos_disciplina' está vazia.")
            else:
                for p in processos:
                    print(f"   - ID: {p.id} | Status: '{p.status}' (Tipo: {type(p.status).__name__}) | Escola ID: {p.aluno.turma.school_id if p.aluno and p.aluno.turma else 'S/ Turma'}")
                print("   [OK] Leitura de dados bem sucedida.")
        except Exception as e:
            print("   [ERRO CRÍTICO] Falha ao ler dados. Provável conflito de ENUM vs STRING.")
            print(f"   Detalhe: {str(e)}")

        # CHECK 3: SIMULAÇÃO DA QUERY DO PAINEL
        print("\n[3] Testando a Query exata do Painel...")
        try:
            # Simula a query usada no JusticaService
            stmt = select(ProcessoDisciplina).join(ProcessoDisciplina.aluno).outerjoin(Aluno.turma)
            resultados = db.session.scalars(stmt).all()
            print(f"   Total de registros encontrados pela query: {len(resultados)}")
            
            if len(resultados) == 0 and processos:
                print("   [ALERTA] Existem processos no banco, mas a query do painel retornou 0.")
                print("   CAUSA PROVÁVEL: O 'join' com Aluno ou Turma está falhando (alunos sem turma ou escola).")
        except Exception as e:
            print(f"   [ERRO] Falha na query do painel: {e}")

if __name__ == "__main__":
    diagnosticar()