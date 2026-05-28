import sys
import cProfile
import pstats
import io
import time

sys.path.insert(0, '.')
from backend.app import create_app
from backend.models.database import db
from backend.models.school import School
from backend.models.edicao import Edicao
from backend.services.dashboard_service import DashboardService
from backend.services.diario_service import DiarioService

def profile_function(func, *args, **kwargs):
    print(f"\n--- Iniciando Perfilamento de: {func.__name__} ---")
    pr = cProfile.Profile()
    
    start_time = time.time()
    pr.enable()
    
    # Executa a função
    result = func(*args, **kwargs)
    
    pr.disable()
    end_time = time.time()
    
    # Prepara a exibição dos resultados
    s = io.StringIO()
    sortby = 'cumulative'  # Ordena pelo tempo total gasto na função (e nas subfunções)
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats(15)  # Imprime as 15 operações mais lentas
    
    print(s.getvalue())
    print(f"Tempo total de execução medido pelo relógio: {end_time - start_time:.4f} segundos")
    print("-" * 50)
    
    return result

def run_tests():
    app = create_app()
    with app.app_context():
        print("Buscando escola de teste...")
        school = School.query.first()
        if not school:
            print("Nenhuma escola encontrada para testar.")
            return
            
        edicao = Edicao.query.filter_by(school_id=school.id).first()
        edicao_id = edicao.id if edicao else None
        
        print(f"Testando na Escola: {school.nome} | Edição: {edicao_id}")
        
        # 1. Teste do Dashboard (Costuma ser pesado pois conta muitas tabelas)
        profile_function(DashboardService.get_dashboard_data, school_id=school.id, edicao_id=edicao_id)
        
        # 2. Teste dos Diários Agrupados (Costuma ser pesado pelas queries N+1)
        profile_function(DiarioService.get_diarios_agrupados, school_id=school.id)

if __name__ == '__main__':
    run_tests()
