import sys
import os

# Adiciona o diretório atual ao path para importar o backend
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
from backend.models.diario_classe import DiarioClasse

app = create_app()

def deletar_diarios():
    with app.app_context():
        print("="*60)
        print("CORREÇÃO DE DIÁRIOS DUPLICADOS")
        print("="*60)
        
        ids_input = input("Digite os IDs dos diários para deletar (separados por vírgula, ex: 105,106): ")
        
        if not ids_input:
            print("Nenhum ID informado. Operação cancelada.")
            return

        try:
            # Converte a string de entrada em uma lista de inteiros
            lista_ids = [int(x.strip()) for x in ids_input.split(',') if x.strip()]
        except ValueError:
            print("Erro: Digite apenas números separados por vírgula.")
            return

        if not lista_ids:
            print("Nenhum ID válido identificado.")
            return

        print(f"\nVocê solicitou a exclusão dos seguintes IDs: {lista_ids}")
        confirmacao = input("Tem certeza que deseja apagar DEFINITIVAMENTE esses registros? (s/n): ")
        
        if confirmacao.lower() != 's':
            print("Operação cancelada.")
            return

        count_sucesso = 0
        count_falha = 0

        for diario_id in lista_ids:
            diario = db.session.get(DiarioClasse, diario_id)
            if diario:
                db.session.delete(diario)
                print(f" -> Diário ID {diario_id} removido.")
                count_sucesso += 1
            else:
                print(f" -> Diário ID {diario_id} não encontrado no banco.")
                count_falha += 1

        if count_sucesso > 0:
            db.session.commit()
            print(f"\nSucesso! {count_sucesso} registros foram apagados do banco de dados.")
            print("A carga horária deve estar corrigida agora.")
        else:
            print("\nNenhum registro foi apagado.")

if __name__ == "__main__":
    deletar_diarios()