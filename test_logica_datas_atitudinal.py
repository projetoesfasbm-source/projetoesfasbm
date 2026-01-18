from datetime import date, timedelta

def verificar_elegibilidade_atitudinal(data_fato, data_inicio_2_ciclo, data_formatura):
    """
    Simula a lógica exata do Art. 125 do Regulamento:
    1. Fato deve ser APÓS o início do 2º Ciclo.
    2. Fato deve ser ANTES dos 40 dias finais.
    """
    print(f"\n--- Analisando Fato: {data_fato} ---")
    
    # 1. Verificação do 2º Ciclo (Art. 121 / 125 §5)
    if data_fato < data_inicio_2_ciclo:
        print(f"❌ REJEITADO: Ocorreu antes do 2º Ciclo ({data_inicio_2_ciclo})")
        return False
    
    # 2. Verificação dos 40 Dias (Art. 125 Caput)
    prazo_limite = data_formatura - timedelta(days=40)
    if data_fato > prazo_limite:
        print(f"❌ REJEITADO: Ocorreu dentro dos 40 dias finais.")
        print(f"   Formatura: {data_formatura}")
        print(f"   Data Limite de Pontuação: {prazo_limite}")
        print(f"   Diferença para formatura: {(data_formatura - data_fato).days} dias")
        return False
        
    print("✅ ACEITO: Pontuação válida para Avaliação Atitudinal.")
    return True

# --- CENÁRIOS DE TESTE ---
if __name__ == "__main__":
    print("=== TESTE DE LÓGICA: REGRA DE DATAS (ART. 125) ===")
    
    # Definição do Cenário
    dt_inicio_ciclo_2 = date(2025, 6, 1)   # 2º Ciclo começou em Junho
    dt_formatura = date(2025, 11, 18)      # Formatura em Novembro
    
    # A) Fato no início do curso (Ex: Abril)
    # Esperado: Não contar (Antes do 2º ciclo)
    verificar_elegibilidade_atitudinal(date(2025, 4, 10), dt_inicio_ciclo_2, dt_formatura)
    
    # B) Fato no meio do curso (Ex: Agosto)
    # Esperado: Contar (Elegível)
    verificar_elegibilidade_atitudinal(date(2025, 8, 15), dt_inicio_ciclo_2, dt_formatura)
    
    # C) Fato FALTANDO 30 DIAS para formatura (Ex: Outubro/Novembro)
    # Limite 40 dias = 18/11 - 40 = 09/Outubro.
    # Fato em 20/Outubro (Faltam 29 dias) -> Deve rejeitar.
    verificar_elegibilidade_atitudinal(date(2025, 10, 20), dt_inicio_ciclo_2, dt_formatura)