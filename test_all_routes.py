import os
import sys

# Adiciona o diretório backend ao PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from app import create_app
from models.database import db
from models.user import User

app = create_app()

def test_routes():
    with app.test_client() as client:
        with app.app_context():
            user = db.session.get(User, 1) # Assumindo ID 1 como admin/programmer para ter acesso total
            
        with client.session_transaction() as sess:
            sess['_user_id'] = str(1)
            sess['active_school_id'] = 1
            sess['active_edicao_id'] = 2  # Testando a Edição 2 (que é nova)
            
        print("Iniciando varredura de rotas GET...")
        errors = []
        tested = 0
        
        for rule in app.url_map.iter_rules():
            if 'GET' in rule.methods:
                url = rule.rule
                if '<' in url:
                    # Rota com parâmetros dinâmicos (tentar mockar os principais)
                    url = url.replace('<int:id>', '1')
                    url = url.replace('<int:school_id>', '1')
                    url = url.replace('<int:aluno_id>', '1')
                    url = url.replace('<int:turma_id>', '1')
                    url = url.replace('<int:disciplina_id>', '1')
                    url = url.replace('<int:semana_id>', '1')
                    url = url.replace('<int:ciclo_id>', '1')
                    url = url.replace('<int:horario_id>', '1')
                    url = url.replace('<int:primeiro_horario_id>', '1')
                    url = url.replace('<path:pelotao>', 'Turma 01')
                    url = url.replace('<filename>', 'teste.txt')
                    
                if '<' in url:
                    # Ignorar rotas que ainda tenham parâmetros que não mockamos
                    continue
                    
                # Ignorar rotas de logout ou destrutivas
                if 'logout' in url or 'delete' in url or 'remover' in url:
                    continue
                    
                tested += 1
                try:
                    response = client.get(url, follow_redirects=True)
                    if response.status_code == 500:
                        errors.append(f"[500] {url}")
                except Exception as e:
                    errors.append(f"[EXCEPTION] {url}: {str(e)}")
                    
        print(f"Testadas {tested} rotas.")
        if errors:
            print("ERROS ENCONTRADOS:")
            for e in errors:
                print(e)
        else:
            print("NENHUM ERRO 500 ENCONTRADO! Sistema estável na Edição 2.")

if __name__ == '__main__':
    test_routes()
