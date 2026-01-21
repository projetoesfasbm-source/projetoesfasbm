import sys
import os
import json
from sqlalchemy import select

# Ajusta o path para encontrar os módulos do backend
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
from backend.models.semana import Semana

app = create_app()

def debug_priority():
    with app.app_context():
        print("\n" + "="*60)
        print("DIAGNÓSTICO DE BLOQUEIOS DE PRIORIDADE (últimas 5 semanas)")
        print("="*60)

        # Busca as últimas 5 semanas para análise
        semanas = db.session.scalars(
            select(Semana).order_by(Semana.id.desc()).limit(5)
        ).all()

        if not semanas:
            print("Nenhuma semana encontrada no banco de dados.")
            return

        for s in semanas:
            print(f"\n>> Semana ID: {s.id} | Nome: {s.nome}")
            print(f"   Período: {s.data_inicio} a {s.data_fim}")
            print(f"   Status Prioridade (priority_active): {s.priority_active}")
            
            # 1. Verifica se a coluna priority_blocks existe no modelo
            if not hasattr(s, 'priority_blocks'):
                print("   [ERRO CRÍTICO] O modelo 'Semana' NÃO possui o atributo 'priority_blocks'.")
                print("   -> Verifique se a migration foi aplicada e se o model 'Semana' foi atualizado.")
                continue

            # 2. Analisa o conteúdo de priority_blocks
            raw_blocks = s.priority_blocks
            print(f"   Conteúdo Raw (Banco): {repr(raw_blocks)}")

            if raw_blocks:
                try:
                    parsed = json.loads(raw_blocks)
                    print("   Conteúdo JSON Interpretado:")
                    # Exibe de forma bonita para facilitar leitura
                    print(json.dumps(parsed, indent=4, ensure_ascii=False))
                    
                    # Teste rápido de estrutura
                    if isinstance(parsed, dict):
                        total_turmas = len(parsed.keys())
                        total_bloqueios = sum(len(dias) for dias in parsed.values())
                        print(f"   [ANÁLISE] Bloqueios definidos para {total_turmas} turmas.")
                    else:
                        print("   [ALERTA] O JSON salvo não é um dicionário (formato incorreto).")
                        
                except json.JSONDecodeError:
                    print("   [ERRO] Falha ao decodificar JSON. O dado no banco está corrompido.")
            else:
                print("   [AVISO] Campo 'priority_blocks' está VAZIO ou NULL.")
                if s.priority_active:
                    print("   -> Se você salvou bloqueios no modal, o Controller não está gravando este campo.")

        print("\n" + "="*60)

if __name__ == "__main__":
    debug_priority()