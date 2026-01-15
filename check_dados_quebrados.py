from backend.app import create_app
from backend.models.database import db
from backend.models.processo_disciplina import ProcessoDisciplina
from backend.models.aluno import Aluno
from backend.models.user import User

app = create_app()

with app.app_context():
    print("\n" + "="*60)
    print("VERIFICAÇÃO DE INTEGRIDADE (BUSCANDO DADOS 'QUEBRADOS')")
    print("="*60)
    
    processos = db.session.query(ProcessoDisciplina).all()
    print(f">> Total de processos encontrados: {len(processos)}")
    
    erros_encontrados = 0
    ids_para_corrigir = []

    for p in processos:
        try:
            # 1. Tenta acessar o Aluno
            aluno = p.aluno
            if aluno is None:
                print(f"[ERRO CRÍTICO] Processo ID {p.id} (Data: {p.data_ocorrencia}) aponta para aluno_id {p.aluno_id} que NÃO EXISTE.")
                erros_encontrados += 1
                ids_para_corrigir.append(p.id)
                continue

            # 2. Tenta acessar o Usuário do Aluno
            user = aluno.user
            if user is None:
                print(f"[ERRO CRÍTICO] O Processo ID {p.id} aponta para o Aluno {aluno.id}, mas esse aluno está sem USUÁRIO (User) vinculado.")
                erros_encontrados += 1
                ids_para_corrigir.append(p.id)
                continue
                
            # 3. Tenta acessar propriedades usadas no template (Nome, etc)
            _ = user.nome_completo
            
        except Exception as e:
            print(f"[FALHA TÉCNICA] Processo ID {p.id} gerou erro ao ler dados: {e}")
            erros_encontrados += 1
            ids_para_corrigir.append(p.id)

    print("\n" + "="*60)
    if erros_encontrados == 0:
        print("SUCESSO: Nenhum dado corrompido foi encontrado nos processos.")
        print("Se o erro persistir, o problema pode estar nas permissões do seu usuário atual.")
    else:
        print(f"ATENÇÃO: Foram encontrados {erros_encontrados} registros quebrados.")
        print("Esses registros estão fazendo a página cair ao tentar carregar o nome do aluno.")
        print(f"IDs dos processos problemáticos: {ids_para_corrigir}")
    print("="*60 + "\n")