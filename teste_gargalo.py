import time
import requests
from concurrent.futures import ThreadPoolExecutor

# ATENÇÃO: Coloque a URL real do seu sistema aqui
URL = "https://esfasbm.pythonanywhere.com/"

def medir_tempo_requisicao(id_req):
    inicio = time.time()
    try:
        # Faz a requisição (timeout de 20s para não prender)
        resposta = requests.get(URL, timeout=20)
        status = resposta.status_code
    except Exception as e:
        status = f"Erro: {e}"
    
    fim = time.time()
    tempo_gasto = fim - inicio
    return id_req, status, tempo_gasto

def executar_teste_individual():
    print(f"--- Teste 1: Única requisição isolada ---")
    _, status, tempo = medir_tempo_requisicao("Isolada")
    print(f"Resultado: Status {status} | Tempo: {tempo:.4f} segundos\n")
    return tempo

def executar_teste_concorrente(num_requisicoes=10):
    print(f"--- Teste 2: {num_requisicoes} requisições SIMULTÂNEAS ---")
    print("Enviando requisições ao mesmo tempo (isso vai testar a fila de workers)...")
    
    inicio_geral = time.time()
    resultados = []
    
    # Inicia as conexões exatamente ao mesmo tempo usando threads
    with ThreadPoolExecutor(max_workers=num_requisicoes) as executor:
        futuros = [executor.submit(medir_tempo_requisicao, i) for i in range(1, num_requisicoes + 1)]
        for futuro in futuros:
            resultados.append(futuro.result())
            
    fim_geral = time.time()
    
    # Exibe os resultados
    for id_req, status, tempo in resultados:
        print(f"Requisição {id_req:02d}: Status {status} | Tempo aguardando resposta: {tempo:.4f} segundos")
        
    print(f"\nTempo TOTAL para o servidor processar todas as {num_requisicoes}: {fim_geral - inicio_geral:.4f} segundos")

if __name__ == "__main__":
    print(f"Iniciando teste de gargalo no servidor: {URL}\n")
    
    tempo_isolado = executar_teste_individual()
    time.sleep(2) # Pausa rápida para o servidor respirar
    executar_teste_concorrente(10)
    
    print("\n--- COMO LER ESSE RESULTADO ---")
    print("Se a 'Única requisição isolada' for rápida (ex: 0.5s), mas nas simultâneas o tempo ")
    print("for subindo gradativamente (0.5s, 1.0s, 1.5s...) e o Tempo TOTAL for alto (ex: 5s),")
    print("está CONFIRMADO: O PythonAnywhere está enfileirando requisições por falta de Workers.")
