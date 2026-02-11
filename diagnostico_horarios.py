import sys
import os
from sqlalchemy import inspect

# --- CONFIGURAÇÃO DE CAMINHO ---
basedir = os.path.abspath(os.path.dirname(__file__))
backend_path = os.path.join(basedir, 'backend')
if os.path.exists(backend_path) and backend_path not in sys.path:
    sys.path.insert(0, backend_path)
# -------------------------------

try:
    from app import create_app
    from models.horario import Horario
    from models.turma import Turma
    
    app = create_app()

    def get_db_session(app_instance):
        if 'sqlalchemy' in app_instance.extensions:
            sa = app_instance.extensions['sqlalchemy']
            if hasattr(sa, 'session'): return sa.session
            elif hasattr(sa, 'db'): return sa.db.session
        from models.database import db
        return db.session

    with app.app_context():
        print("="*50)
        print("DIAGNÓSTICO AUTO-ADAPTÁVEL")
        print("="*50)

        session = get_db_session(app)

        # 1. DESCOBRIR O NOME CORRETO DA COLUNA
        # Pega todas as colunas mapeadas no modelo Horario
        columns = [c.key for c in Horario.__table__.columns]
        print(f"Colunas encontradas no modelo Horario: {columns}")

        # Tenta achar a coluna que parece ser o ID da turma
        coluna_turma_nome = None
        candidatos = ['turma_id', 'id_turma', 'turmaId', 'turma_id_fk', 'idTurma']
        
        # Primeiro, verifica se algum dos nomes padrões existe
        for c in candidatos:
            if c in columns:
                coluna_turma_nome = c
                break
        
        # Se não achou, tenta achar qualquer coluna que contenha "turma" e "id"
        if not coluna_turma_nome:
            for c in columns:
                if 'turma' in c.lower() and ('id' in c.lower() or 'fk' in c.lower()):
                    coluna_turma_nome = c
                    break

        if not coluna_turma_nome:
            print("\n[ERRO] Não consegui identificar qual coluna liga o Horário à Turma.")
            print("Por favor, verifique o arquivo 'models/horario.py' e veja o nome da ForeignKey.")
            sys.exit(1)

        print(f">> Coluna de vínculo identificada: '{coluna_turma_nome}'")
        
        # Obtém o atributo real da classe baseado no nome descoberto
        attr_turma_id = getattr(Horario, coluna_turma_nome)

        # 2. BUSCA POR FANTASMAS (Usando o atributo correto)
        print("\n[BUSCANDO VÍNCULOS QUEBRADOS...]")
        
        fantasmas = session.query(Horario)\
            .outerjoin(Turma, attr_turma_id == Turma.id)\
            .filter(attr_turma_id != None)\
            .filter(Turma.id == None)\
            .all()
        
        qtd_fantasmas = len(fantasmas)

        if qtd_fantasmas > 0:
            print(f"\n[!!! PROBLEMA ENCONTRADO !!!]")
            print(f"Existem {qtd_fantasmas} horários 'fantasmas'.")
            print(f"Eles têm '{coluna_turma_nome}' preenchido, mas a Turma não existe.")
            
            # Exibir amostra
            print(f"Exemplos de IDs com erro: {[h.id for h in fantasmas[:5]]}...")

            # PERGUNTA DE LIMPEZA
            print("\n" + "!"*40)
            print("Deseja EXCLUIR esses horários inválidos?")
            resp = input("Digite 'SIM' para limpar: ")
            
            if resp.strip().upper() == 'SIM':
                try:
                    for f in fantasmas:
                        session.delete(f)
                    session.commit()
                    print(f"\n>> SUCESSO: {qtd_fantasmas} registros limpos.")
                except Exception as e:
                    session.rollback()
                    print(f"Erro ao tentar apagar: {e}")
        else:
            print(">> Tudo limpo! Não existem horários sem turma válida.")

except ImportError as e:
    print(f"Erro crítico: {e}")
except Exception as e:
    print(f"Erro inesperado: {e}")