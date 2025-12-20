import sys
import os
from unittest.mock import MagicMock

# ==============================================================================
# HACK: MOCK DE DEPENDÊNCIAS EXTERNAS
# Engana o Python para não quebrar se faltarem bibliotecas que o script NÃO usa
# mas que são importadas pelo 'app.py' (como Firebase ou python-docx).
# ==============================================================================
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.auth"] = MagicMock()
sys.modules["docx"] = MagicMock()
sys.modules["docx.shared"] = MagicMock()
sys.modules["docx.enum.text"] = MagicMock()
# ==============================================================================

from datetime import date, timedelta
from sqlalchemy import select, or_, and_

# Adiciona o diretório pai ao path para importar o backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from backend.app import create_app
    from backend.models.database import db
    from backend.models.disciplina import Disciplina
    from backend.models.horario import Horario
    from backend.models.semana import Semana
    from backend.models.turma import Turma
except ImportError as e:
    print(f"ERRO DE IMPORTAÇÃO: {e}")
    print("Verifique se você está rodando o script da raiz do projeto ou da pasta scripts.")
    sys.exit(1)

app = create_app()

def get_dia_offset(dia_str):
    s = dia_str.lower().strip()
    if 'segunda' in s: return 0
    if 'terca' in s or 'terça' in s: return 1
    if 'quarta' in s: return 2
    if 'quinta' in s: return 3
    if 'sexta' in s: return 4
    if 'sabado' in s or 'sábado' in s: return 5
    if 'domingo' in s: return 6
    return 0

def calcular_horas_reais(disciplina):
    """
    Simula a lógica de cálculo do quadro de horários com deduplicação.
    """
    today = date.today()
    today_weekday_index = today.weekday()
    dias_da_semana = ['segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado', 'domingo']
    dias_passados = dias_da_semana[:today_weekday_index + 1]

    # Busca as aulas que já ocorreram (status confirmado)
    query = (
        select(Horario, Semana)
        .join(Semana)
        .where(
            Horario.disciplina_id == disciplina.id,
            Horario.status == 'confirmado',
            or_(
                Semana.data_fim < today,
                and_(
                    Semana.data_inicio <= today,
                    Semana.data_fim >= today,
                    Horario.dia_semana.in_(dias_passados)
                )
            )
        )
    )
    
    rows = db.session.execute(query).all()
    
    slots_computados = set()
    total_horas = 0
    detalhes = []
    
    for row in rows:
        horario = row[0]
        semana = row[1]
        
        offset = get_dia_offset(horario.dia_semana)
        data_aula = semana.data_inicio + timedelta(days=offset)
        
        # Chave de Unicidade: Data + Periodo + Pelotao
        # Se houver 2 instrutores na mesma aula, esta chave será idêntica para ambos
        chave = (data_aula, horario.periodo, horario.pelotao)
        
        if chave not in slots_computados:
            duracao = horario.duracao or 1
            total_horas += duracao
            slots_computados.add(chave)
            
            detalhes.append({
                'data': data_aula,
                'dia': horario.dia_semana,
                'periodo': horario.periodo,
                'duracao': duracao,
                'pelotao': horario.pelotao,
                'instrutor_1': horario.instrutor_id,
                'instrutor_2': horario.instrutor_id_2
            })
            
    return total_horas, detalhes

def diagnosticar_disciplinas():
    print("="*80)
    print("INICIANDO DIAGNÓSTICO DE HORAS-AULA")
    print("="*80)
    
    with app.app_context():
        # Busca todas as disciplinas que possuem carga horária definida
        disciplinas = db.session.scalars(select(Disciplina).where(Disciplina.carga_horaria_prevista > 0).order_by(Disciplina.materia)).all()
        
        problemas_encontrados = 0
        
        for disciplina in disciplinas:
            # 1. Valor salvo no Banco (campo 'carga_horaria_cumprida')
            valor_banco = float(disciplina.carga_horaria_cumprida or 0)
            
            # 2. Valor calculado dinamicamente do Quadro de Horários (com a correção de deduplicação)
            calculo_dinamico, detalhes_slots = calcular_horas_reais(disciplina)
            
            prevista = float(disciplina.carga_horaria_prevista or 0)
            
            # 3. Simulação do Erro: O que o usuário vê na tela?
            valor_soma_indevida = valor_banco + calculo_dinamico
            
            # Verifica inconsistências
            tem_erro = False
            tipo_erro = ""

            # Caso 1: O sistema visual soma indevidamente
            if valor_soma_indevida > prevista and prevista > 0:
                if valor_banco > 0 and calculo_dinamico > 0:
                    tem_erro = True
                    tipo_erro = "DUPLA CONTAGEM (Banco + Quadro)"
            
            # Caso 2: O valor do banco já está maior que a prevista
            if valor_banco > prevista:
                tem_erro = True
                tipo_erro = f"BANCO EXCEDIDO ({valor_banco} > {prevista})"

            if tem_erro:
                problemas_encontrados += 1
                turma_nome = disciplina.turma.nome if disciplina.turma else "Sem Turma"
                
                print(f"\n[ALERTA] Disciplina: {disciplina.materia} (ID: {disciplina.id}) | Turma: {turma_nome}")
                print(f"         Carga Prevista: {prevista}")
                print("-" * 60)
                print(f"         [A] Salvo no Banco (Diários/Sync): {valor_banco}")
                print(f"         [B] Calculado do Quadro (Grade):   {calculo_dinamico}")
                print(f"         [A+B] Valor Visual Atual:          {valor_soma_indevida}")
                print("-" * 60)
                print(f"         DIAGNÓSTICO: {tipo_erro}")
                
                if calculo_dinamico > 0:
                    print("         > Detalhes das Aulas no Quadro (Deduplicadas):")
                    detalhes_slots.sort(key=lambda x: x['data'])
                    for slot in detalhes_slots:
                        dupla_aviso = " (DUPLA)" if slot['instrutor_2'] else ""
                        print(f"           - {slot['data'].strftime('%d/%m')} | Per:{slot['periodo']} | {slot['duracao']}h | Pel:{slot['pelotao']}{dupla_aviso}")
                
                print("="*80)

        if problemas_encontrados == 0:
            print("\nNenhuma extrapolação óbvia encontrada baseada na soma (Banco + Quadro).")
        else:
            print(f"\nForam encontradas {problemas_encontrados} disciplinas com problemas.")
            print("SOLUÇÃO:")
            print("1. Se apareceu 'DUPLA CONTAGEM': O backend está somando indevidamente. O código anterior que enviei já corrige isso.")
            print("   (Verifique se aplicou o arquivo 'disciplina_service.py' completo).")
            print("2. Se apareceu 'BANCO EXCEDIDO': Clique no botão 'Sincronizar' na página de disciplinas.")

if __name__ == "__main__":
    diagnosticar_disciplinas()