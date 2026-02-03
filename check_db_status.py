# check_db_status.py
import os
import sys
from collections import Counter

# Adiciona o diretório atual ao path para encontrar o pacote backend
sys.path.append(os.getcwd())

try:
    from backend.app import create_app
    from backend.models.database import db
    from backend.models.horario import Horario
    from sqlalchemy import func
except ImportError as e:
    print(f"Erro ao importar módulos: {e}")
    sys.exit(1)

app = create_app()

with app.app_context():
    print("="*50)
    print("DIAGNÓSTICO EXATO DE STATUS DAS AULAS")
    print("="*50)

    # 1. Contagem Geral por Status
    status_count = db.session.query(Horario.status, func.count(Horario.id)).group_by(Horario.status).all()
    
    print("\n[1] DISTRIBUIÇÃO DE STATUS NO BANCO:")
    if not status_count:
        print("Nenhuma aula encontrada na tabela 'horarios'.")
    else:
        for status, total in status_count:
            status_label = f"'{status}'" if status is not None else "NULL (Vazio)"
            print(f" - Status {status_label.ljust(15)} : {total} aulas")

    # 2. Amostragem de registros para verificar o conteúdo real
    print("\n[2] AMOSTRAGEM DE REGISTROS (ÚLTIMOS 10):")
    aulas = Horario.query.order_by(Horario.id.desc()).limit(10).all()
    
    for a in aulas:
        status_real = f"'{a.status}'" if a.status is not None else "NULL"
        print(f"ID: {a.id} | Pelotão: {a.pelotao} | Disciplina ID: {a.disciplina_id} | Status: {status_real}")

    # 3. Verificação de inconsistência de Pelotão (Vínculo que você mencionou)
    print("\n[3] VERIFICAÇÃO DE DADOS DE PELOTÃO:")
    pelotoes = db.session.query(Horario.pelotao, func.count(Horario.id)).group_by(Horario.pelotao).limit(5).all()
    for p, total in pelotoes:
        print(f" - Pelotão: {p if p else 'SEM NOME'} | Aulas: {total}")

    print("\n" + "="*50)
    print("FIM DO DIAGNÓSTICO")
    print("="*50)