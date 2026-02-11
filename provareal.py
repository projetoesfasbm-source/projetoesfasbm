import os
import sys
sys.path.append(os.getcwd())
from backend.app import create_app
from backend.models.database import db
from backend.models.horario import Horario

app = create_app()
with app.app_context():
    print("=== OPERAÇÃO LIMPEZA TOTAL: AGENDAMENTOS E FINANCEIRO ===\n")
    
    # Contagem de segurança
    total_antes = Horario.query.count()
    
    print(f"ATENÇÃO: Este script irá DELETAR DEFINITIVAMENTE os {total_antes} registros de aulas.")
    print("Isso zerará os quadros, diários e folhas de pagamento de TODAS as escolas.\n")
    
    confirmar1 = input("Tem certeza absoluta que deseja zerar TUDO? (s/n): ")
    if confirmar1.lower() == 's':
        confirmar2 = input("Esta ação NÃO TEM VOLTA. Digite 'DELETAR' para confirmar: ")
        
        if confirmar2 == "DELETAR":
            try:
                # Executa a limpeza total da tabela
                db.session.query(Horario).delete()
                db.session.commit()
                print(f"\n[SUCESSO] {total_antes} registros apagados.")
                print("O sistema está agora com o quadro horário 100% limpo.")
            except Exception as e:
                db.session.rollback()
                print(f"\n[ERRO] Ocorreu uma falha ao tentar deletar: {e}")
        else:
            print("\n[CANCELADO] A frase de confirmação não foi digitada corretamente.")
    else:
        print("\n[CANCELADO] Nenhuma alteração foi feita.")