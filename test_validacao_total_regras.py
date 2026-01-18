import sys
import os
from datetime import date, timedelta

# Simulação das Classes (Mock) para não depender do banco ainda
class MockSchool:
    def __init__(self, tipo): self.npccal_type = tipo

class MockTurma:
    def __init__(self, school_tipo, dt_inicio_2_ciclo, dt_formatura):
        self.school = MockSchool(school_tipo)
        self.dt_inicio_2_ciclo = dt_inicio_2_ciclo
        self.data_formatura = dt_formatura

def calcular_pontos_teste(turma, tipo_infracao, data_fato):
    """
    Simula a lógica FINAL que irá para o JusticaService.
    Retorna TRUE se a infração deve descontar nota, FALSE se não.
    """
    # 1. Filtro CTSP (Nunca pontua)
    if turma.school.npccal_type == 'cfs':
        return False, "CTSP não pontua"

    # 2. Trava dos 40 Dias (Vale para TUDO em curso pontuado)
    if turma.data_formatura:
        limite_final = turma.data_formatura - timedelta(days=40)
        if data_fato > limite_final:
            return False, "Bloqueado: 40 dias finais"

    # 3. Regra de Início (Art 125)
    # Crime/RDBM: Conta sempre (dentro do limite final)
    if tipo_infracao in ['CRIME', 'RDBM']:
        return True, "Crime/RDBM conta desde o início"
    
    # NPCCAL: Só conta após o 2º Ciclo
    if tipo_infracao == 'NPCCAL':
        if not turma.dt_inicio_2_ciclo:
            return False, "Sem data de 2º ciclo definida"
        if data_fato < turma.dt_inicio_2_ciclo:
            return False, "Antes do 2º Ciclo"
            
    return True, "Pontuação Válida"

def executar_bateria_testes():
    print("=== BATERIA DE TESTES: REGRAS COMPLEXAS (ART. 125) ===\n")
    
    # DATAS BASE
    hoje = date(2026, 5, 10)
    dt_2_ciclo = date(2026, 6, 1)      # 2º Ciclo começa em Junho
    dt_formatura = date(2026, 11, 20)  # Formatura Novembro
    dt_40_dias = dt_formatura - timedelta(days=40) # 11/10/2026
    
    # CENÁRIOS
    cenarios = [
        # --- ESCOLA CTSP (O "Imune") ---
        {"escola": "cfs", "fato": "NPCCAL", "data": hoje, "esperado": False, "desc": "CTSP Início"},
        {"escola": "cfs", "fato": "CRIME",  "data": hoje, "esperado": False, "desc": "CTSP Crime"},
        
        # --- ESCOLA CBFPM/CSPM (Pontuadas) ---
        
        # 1. NPCCAL Antes do 2º Ciclo (Não deve contar)
        {"escola": "cbfpm", "fato": "NPCCAL", "data": date(2026, 5, 20), "esperado": False, "desc": "NPCCAL antes 2º ciclo"},
        
        # 2. CRIME Antes do 2º Ciclo (Deve contar - Art 125 §6)
        {"escola": "cbfpm", "fato": "CRIME", "data": date(2026, 5, 20), "esperado": True,  "desc": "Crime antes 2º ciclo"},
        
        # 3. NPCCAL Durante 2º Ciclo (Deve contar)
        {"escola": "cspm",  "fato": "NPCCAL", "data": date(2026, 8, 15), "esperado": True,  "desc": "NPCCAL no período válido"},
        
        # 4. NPCCAL nos 40 Dias Finais (Não deve contar)
        # Limite é 11/Out. Fato em 01/Nov.
        {"escola": "cbfpm", "fato": "NPCCAL", "data": date(2026, 11, 1), "esperado": False, "desc": "NPCCAL nos 40 dias finais"},
        
        # 5. CRIME nos 40 Dias Finais (Não deve contar na NOTA, embora o fato exista)
        {"escola": "cbfpm", "fato": "CRIME", "data": date(2026, 11, 1), "esperado": False, "desc": "Crime nos 40 dias finais"}
    ]

    erros = 0
    for i, c in enumerate(cenarios):
        turma = MockTurma(c['escola'], dt_2_ciclo, dt_formatura)
        resultado, motivo = calcular_pontos_teste(turma, c['fato'], c['data'])
        
        status = "✅ PASSOU" if resultado == c['esperado'] else "❌ FALHOU"
        if resultado != c['esperado']: erros += 1
        
        print(f"Teste {i+1} [{c['desc']}]: {status} | Motivo: {motivo}")

    print(f"\nResultado: {len(cenarios) - erros}/{len(cenarios)} testes aprovados.")
    if erros == 0:
        print(">> A Lógica cobre todos os regulamentos (CTSP, Prazos e Tipos de Infração).")
    else:
        print(">> A Lógica precisa de ajustes.")

if __name__ == "__main__":
    executar_bateria_testes()