import os

files_to_check = [
    'backend/maintenance/force_recreate_disciplinas.py',  # SUSPEITO Nº 1
    'backend/controllers/vinculo_controller.py',          # Onde se gerencia vínculos
    'backend/models/disciplina.py',                       # Verificar se tem cascade="all, delete"
    'backend/services/turma_service.py',                  # Verificar lógica de sync
]

print("="*80)
print("🕵️  INVESTIGAÇÃO DE CÓDIGO FONTE - PROCURANDO 'DELETE'")
print("="*80)

for file_path in files_to_check:
    print(f"\n📂 Lendo arquivo: {file_path}")
    print("-" * 80)
    
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Vamos focar em linhas que contenham 'delete', 'remove' ou 'cascade'
                lines = content.split('\n')
                found_danger = False
                for i, line in enumerate(lines):
                    if any(x in line for x in ['delete', 'remove', 'cascade', 'session.query']):
                        print(f"{i+1}: {line.strip()}")
                        found_danger = True
                
                if not found_danger:
                    print("   (Nenhuma palavra-chave 'delete/remove/cascade' encontrada neste arquivo)")
        except Exception as e:
            print(f"❌ Erro ao ler arquivo: {e}")
    else:
        print("❌ Arquivo não encontrado.")
    print("-" * 80)