# scripts/batch_pre_register_alunos.py

import sys
import os
from dotenv import load_dotenv

# --- CONFIGURAÇÃO IMPORTANTE ---
# Antes de rodar, defina o ID da escola na qual os alunos serão cadastrados.
# Se você tiver apenas uma escola, o ID provavelmente é 1.
# Verifique o ID correto no painel de Super Admin -> Gerenciar Escolas.
SCHOOL_ID_PARA_CADASTRO = 1
# -----------------------------


def pre_cadastrar_alunos_em_lote():
    """
    Lê uma lista de matrículas de um arquivo e realiza o pré-cadastro
    em lote para o perfil de 'aluno' em uma escola específica.
    """
    print("Iniciando script de pré-cadastro em lote...")

    # Adiciona o diretório raiz do projeto ao path para encontrar os módulos
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(project_root)
    
    # Carrega as variáveis de ambiente do arquivo .env
    env_path = os.path.join(project_root, '.env')
    load_dotenv(env_path)

    # Importa os componentes necessários da aplicação
    try:
        from backend.app import create_app
        from backend.services.user_service import UserService
    except ImportError as e:
        print(f"Erro ao importar módulos: {e}")
        print("Certifique-se de que o script está no lugar correto e o virtualenv está ativo.")
        return

    # 1. Ler as matrículas do arquivo de texto
    caminho_arquivo_ids = os.path.join(project_root, 'todos alunos ID FUNC.txt')
    try:
        with open(caminho_arquivo_ids, 'r') as f:
            # Lê todas as linhas, remove espaços em branco e ignora a primeira linha (cabeçalho) e linhas vazias
            matriculas = [line.strip() for line in f.readlines()[1:] if line.strip()]
        print(f"Encontradas {len(matriculas)} matrículas no arquivo.")
    except FileNotFoundError:
        print(f"ERRO: O arquivo 'todos alunos ID FUNC.txt' não foi encontrado no diretório principal do projeto.")
        return

    # 2. Executar o serviço dentro do contexto da aplicação
    app = create_app()
    with app.app_context():
        print(f"Realizando pré-cadastro para a Escola ID: {SCHOOL_ID_PARA_CADASTRO}...")
        
        # Chama o serviço para realizar o pré-cadastro em lote
        success, novos, existentes = UserService.batch_pre_register_users(
            matriculas=matriculas,
            role='aluno', # Define a função como 'aluno'
            school_id=SCHOOL_ID_PARA_CADASTRO
        )

        # 3. Exibir o resultado
        if success:
            print("\n--- RESULTADO ---")
            print(f"Operação concluída com sucesso!")
            print(f"Novos usuários pré-cadastrados: {novos}")
            print(f"Usuários que já existiam: {existentes}")
            print("-----------------\n")
        else:
            print("\n--- ERRO ---")
            print("Ocorreu um erro durante o pré-cadastro em lote.")
            print("-----------------\n")


# Ponto de entrada para execução direta do script
if __name__ == '__main__':
    pre_cadastrar_alunos_em_lote()