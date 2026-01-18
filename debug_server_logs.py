import sys
import os
import traceback

print("=== DIAGNÓSTICO DE INICIALIZAÇÃO DO FLASK ===")
print(f"Diretório atual: {os.getcwd()}")

try:
    print("1. Tentando importar create_app...")
    from backend.app import create_app
    
    print("2. Tentando criar a aplicação (isso carrega os models e services)...")
    app = create_app()
    print("✅ SUCESSO: A aplicação carregou sem erros fatais.")
    print("   Se as abas sumiram, pode ser um problema de permissão (role) ou template.")

except ImportError as e:
    print("\n❌ ERRO CRÍTICO DE IMPORTAÇÃO:")
    print(f"   O Python não conseguiu carregar um arquivo. Geralmente é Import Circular.")
    print(f"   Detalhe: {e}")
    print("\n   RASTREAMENTO:")
    traceback.print_exc()

except SyntaxError as e:
    print("\n❌ ERRO DE SINTAXE (Código escrito errado):")
    print(f"   Arquivo: {e.filename}, Linha: {e.lineno}")
    print(f"   Erro: {e.msg}")

except Exception as e:
    print(f"\n❌ ERRO GENÉRICO AO INICIAR:")
    print(f"   {e}")
    traceback.print_exc()

print("\n=== VERIFICAÇÃO ESPECÍFICA DE SERVICES ===")
try:
    print("3. Testando importação isolada do JusticaService...")
    from backend.services.justica_service import JusticaService
    print("✅ JusticaService importado com sucesso.")
except Exception as e:
    print(f"❌ Falha ao importar JusticaService: {e}")