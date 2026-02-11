import os
import sys
import uuid
sys.path.append(os.getcwd())
from backend.app import create_app
from backend.models.database import db
from backend.models.horario import Horario

app = create_app()
with app.app_context():
    print("=== RESTAURAÇÃO DE EMERGÊNCIA: QUADRO E FINANCEIRO ===\n")
    
    # 1. Limpeza para evitar erros de duplicidade e conflitos de horários
    print("Limpando registros residuais para evitar conflitos...")
    db.session.query(Horario).delete()
    db.session.flush()

    # 2. Leitura do Backup Mestre (O arquivo com 12 mil linhas)
    # Certifique-se de que o nome do arquivo abaixo é o correto
    arquivo_backup = 'RESTAURACAO_MASTER.txt'
    
    with open(arquivo_backup, 'r', encoding='utf-8') as f:
        linhas = f.readlines()[1:] # Pula o cabeçalho

    total_recuperado = 0
    print(f"Iniciando processamento de {len(linhas)} registros...")

    for linha in linhas:
        p = linha.strip().split('|')
        if len(p) < 10: continue

        # Recriamos a aula com todos os vínculos originais
        # Isso é o que recupera o relatório de pagamento (instrutor_id + disciplina_id)
        nova_aula = Horario(
            pelotao=p[0],
            semana_id=int(p[1]),
            dia_semana=p[2],
            periodo=int(p[3]),
            duracao=int(p[4]),
            disciplina_id=int(p[5]),
            instrutor_id=int(p[6]) if p[6] != 'None' else None,
            instrutor_id_2=int(p[7]) if p[7] != 'None' else None,
            status=p[8],
            observacao=p[9] if p[9] != 'None' else None,
            group_id=str(uuid.uuid4()) if int(p[4]) > 1 else None
        )
        db.session.add(nova_aula)
        total_recuperado += 1
        
        # Commits parciais para não sobrecarregar a memória
        if total_recuperado % 1000 == 0:
            db.session.flush()
            print(f" -> {total_recuperado} aulas processadas...")

    confirmar = input(f"\nConfirmar a restauração de {total_recuperado} aulas? (s/n): ")
    if confirmar.lower() == 's':
        db.session.commit()
        print("\n[SUCESSO] O sistema foi restaurado.")
        print("Verifique o quadro horário e o relatório de pagamentos agora.")
    else:
        db.session.rollback()
        print("\n[ABORTADO] Nenhuma alteração foi feita.")