import sys
import os

sys.path.append(os.getcwd())

print("1. Tentando importar App...")
try:
    from backend.app import create_app
    app = create_app()
    print("   [OK] App criado.")
except Exception as e:
    print(f"   [ERRO FATAL] App: {e}")
    sys.exit(1)

print("\n2. Tentando importar Modelos...")
try:
    from backend.models.fada_avaliacao import FadaAvaliacao
    print("   [OK] Modelo FadaAvaliacao encontrado.")
except ImportError:
    print("   [ERRO FATAL] Arquivo 'backend/models/fada_avaliacao.py' não existe ou erro de nome.")
    sys.exit(1)
except Exception as e:
    print(f"   [ERRO] No modelo FADA: {e}")

print("\n3. Tentando importar Service (Justiça)...")
try:
    from backend.services.justica_service import JusticaService
    print("   [OK] Service carregado.")
except Exception as e:
    print(f"   [ERRO FATAL] Erro no JusticaService: {e}")
    # Mostra onde está o erro
    import traceback
    traceback.print_exc()

print("\n4. Tentando importar Controller...")
try:
    from backend.controllers.justica_controller import justica_bp
    print("   [OK] Controller carregado.")
except Exception as e:
    print(f"   [ERRO FATAL] Erro no JusticaController: {e}")
    import traceback
    traceback.print_exc()