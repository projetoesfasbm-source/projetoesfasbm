from backend.app import create_app
from backend.models.database import db
from backend.models.processo_disciplina import ProcessoDisciplina
from sqlalchemy import text

def diagnosticar():
    app = create_app()
    with app.app_context():
        print("\n" + "="*50)
        print("DIAGNÓSTICO DE STATUS DOS PROCESSOS")
        print("="*50)
        
        # 1. Pega os últimos 5 processos que deveriam estar "Aguardando"
        # Usamos SQL puro para ver o dado BRUTO, sem filtros do SQLAlchemy
        sql = text("""
            SELECT id, status, aluno_id 
            FROM processos_disciplina 
            ORDER BY id DESC 
            LIMIT 5
        """)
        
        with db.engine.connect() as conn:
            result = conn.execute(sql)
            
            print(f"{'ID':<6} | {'STATUS (Banco)':<25} | {'STATUS (Interpretado)'}")
            print("-" * 60)
            
            for row in result:
                pid, raw_status, aid = row.id, row.status, row.aluno_id
                
                # Simula a lógica do template Jinja
                try:
                    status_str = str(raw_status).upper()
                    tem_aguardando = 'AGUARDANDO' in status_str
                    tem_notificado = 'NOTIFICADO' in status_str
                    
                    interpretacao = "NADA"
                    if tem_aguardando: interpretacao = "BOTÃO CIENTE [OK]"
                    elif tem_notificado: interpretacao = "BOTÃO DEFESA [OK]"
                    else: interpretacao = "SEM BOTÃO [ERRO?]"
                    
                    print(f"{pid:<6} | {str(raw_status):<25} | {interpretacao}")
                    
                    # Verificação de caracteres invisíveis
                    if raw_status:
                        debug_chars = [f"{ord(c)}" for c in raw_status if ord(c) > 126 or ord(c) < 32]
                        if debug_chars:
                            print(f"       [ALERTA] Caracteres estranhos detectados: {debug_chars}")
                            
                except Exception as e:
                    print(f"{pid:<6} | ERRO AO PROCESSAR: {e}")

        print("\n" + "="*50)
        print("Se a coluna do meio mostrar algo diferente de 'AGUARDANDO_CIENCIA',")
        print("o script de correção de banco precisa ser ajustado.")

if __name__ == "__main__":
    diagnosticar()