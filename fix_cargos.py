# fix_cargos.py
import sys
import os
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
from backend.models.turma_cargo import TurmaCargo

app = create_app()

with app.app_context():
    print("--- CORRIGINDO NOMES DE CARGOS ---")
    
    # 1. Pega todos os cargos
    cargos = db.session.query(TurmaCargo).all()
    count = 0
    
    for c in cargos:
        original = c.cargo_nome
        
        # Lógica de correção: Se parecer com Chefe, vira o OFICIAL
        if 'chefe' in original.lower() and 'sub' not in original.lower():
            if original != TurmaCargo.ROLE_CHEFE:
                c.cargo_nome = TurmaCargo.ROLE_CHEFE
                print(f"Corrigido: '{original}' -> '{TurmaCargo.ROLE_CHEFE}' (Turma ID: {c.turma_id})")
                count += 1
        
        elif 'sub' in original.lower() and 'chefe' in original.lower():
             if original != TurmaCargo.ROLE_SUBCHEFE:
                c.cargo_nome = TurmaCargo.ROLE_SUBCHEFE
                print(f"Corrigido: '{original}' -> '{TurmaCargo.ROLE_SUBCHEFE}'")
                count += 1

    if count > 0:
        db.session.commit()
        print(f"✅ SUCESSO: {count} cargos foram padronizados no banco de dados.")
    else:
        print("✅ Tudo certo: Nenhum cargo precisou ser corrigido ou nenhum cargo encontrado.")