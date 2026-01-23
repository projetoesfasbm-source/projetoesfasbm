import sys
import os
import json

# Adiciona o diretório atual ao path para importar os módulos do backend
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
from backend.models.semana import Semana

app = create_app()

def limpar_apenas_bloqueios_periodo():
    """
    Remove APENAS o JSON de 'priority_blocks' (Bloqueio de Período),
    MANTENDO o 'priority_active' e 'priority_disciplines' (Modo Prioridade).
    """
    with app.app_context():
        print("="*60)
        print("LIMPEZA DE BLOQUEIOS DE PERÍODO (MANTENDO PRIORIDADE DE DISCIPLINA)")
        print("="*60)

        # Busca todas as semanas
        todas_semanas = db.session.query(Semana).all()
        
        count_fixed = 0
        
        for semana in todas_semanas:
            # Verifica se tem bloqueios de períodos salvos
            raw_blocks = getattr(semana, 'priority_blocks', '{}')
            
            # Se tiver conteúdo diferente de vazio, limpa
            if raw_blocks and raw_blocks != '{}' and raw_blocks != 'null':
                print(f"[CORRIGINDO] Semana '{semana.nome}' (ID {semana.id}): Removendo bloqueios de período.")
                semana.priority_blocks = '{}' # Zera apenas os bloqueios de período
                count_fixed += 1
            
            # NÃO MEXEMOS EM priority_active nem priority_disciplines

        if count_fixed > 0:
            try:
                db.session.commit()
                print(f"\n✅ SUCESSO: {count_fixed} semanas tiveram os bloqueios de período removidos.")
            except Exception as e:
                db.session.rollback()
                print(f"\n❌ ERRO ao salvar no banco: {e}")
        else:
            print("\n✅ Nenhuma semana precisou de correção (nenhum bloqueio de período encontrado).")

        print("="*60)

if __name__ == "__main__":
    limpar_apenas_bloqueios_periodo()