import sys
import os
from sqlalchemy import text

# Configuração de caminho
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from backend.app import create_app
from backend.models.database import db
from backend.models.user import User
from backend.models.aluno import Aluno
from backend.models.turma import Turma
from backend.models.user_school import UserSchool
from backend.models.diario_classe import DiarioClasse
from backend.models.turma_cargo import TurmaCargo # Necessário para achar o chefe

app = create_app()

def transferir_para_chefe_e_deletar():
    with app.app_context():
        BAD_ID = 610
        ROLE_CHEFE_NAME = "Chefe de Turma" # Nome exato do cargo no banco
        
        print(f"\n=== TRANSFERÊNCIA PARA CHEFE DE TURMA E REMOÇÃO: ID {BAD_ID} ===")
        
        # 1. Busca o usuário que será apagado
        bad_user = db.session.get(User, BAD_ID)
        if not bad_user:
            print(f"Erro: Usuário ID {BAD_ID} não encontrado.")
            return

        print(f"Usuário ALVO: {bad_user.nome_completo} (ID: {bad_user.id})")

        # 2. Busca Diários vinculados
        diarios = DiarioClasse.query.filter_by(responsavel_id=BAD_ID).all()
        
        todos_transferidos = True
        
        if diarios:
            print(f"\n[!] Existem {len(diarios)} diários assinados por este usuário.")
            
            for diario in diarios:
                turma = diario.turma
                if not turma:
                    print(f"    [ERRO] Diário ID {diario.id} não tem turma vinculada. Impossível achar chefe.")
                    todos_transferidos = False
                    continue

                # 3. Busca o Chefe daquela Turma
                # Procura na tabela de cargos quem é o chefe da turma do diário
                cargo_chefe = TurmaCargo.query.filter_by(
                    turma_id=turma.id, 
                    cargo_nome=ROLE_CHEFE_NAME
                ).first()
                
                chefe_real = None
                if cargo_chefe:
                    aluno_chefe = db.session.get(Aluno, cargo_chefe.aluno_id)
                    if aluno_chefe and aluno_chefe.user_id != BAD_ID:
                        chefe_real = aluno_chefe.user
                
                if chefe_real:
                    print(f"    -> Diário {diario.id} (Turma '{turma.nome}'): Transferindo para Chefe {chefe_real.nome_completo} (ID {chefe_real.id})")
                    diario.responsavel_id = chefe_real.id
                    
                    obs = diario.observacoes or ""
                    if "[Autoria transferida" not in obs:
                        diario.observacoes = f"{obs} [Transferido do ID {BAD_ID} para Chefe {chefe_real.nome_de_guerra}]"
                else:
                    print(f"    [FALHA] Turma '{turma.nome}' NÃO tem Chefe de Turma definido (ou o chefe é o próprio 610).")
                    print("            Defina um Chefe de Turma para esta turma no painel antes de rodar o script.")
                    todos_transferidos = False

        else:
            print("\n[OK] Nenhum diário encontrado para transferir.")

        # 4. Só deleta se TUDO foi resolvido
        if todos_transferidos:
            try:
                print("\n[OK] Todos os diários foram transferidos. Iniciando exclusão...")
                
                # Remove Vínculos
                Aluno.query.filter_by(user_id=BAD_ID).delete()
                UserSchool.query.filter_by(user_id=BAD_ID).delete()
                
                # Se ele tinha algum cargo (ex: era chefe antigo), remove também
                aluno_profile_temp = db.session.scalar(text(f"SELECT id FROM alunos WHERE user_id = {BAD_ID}"))
                if aluno_profile_temp:
                    TurmaCargo.query.filter_by(aluno_id=aluno_profile_temp).delete()

                # Remove User
                db.session.delete(bad_user)
                db.session.commit()
                print(f"\nSUCESSO: Usuário {BAD_ID} removido e diários preservados com os Chefes de Turma.")
                
            except Exception as e:
                db.session.rollback()
                print(f"Erro ao deletar: {str(e)}")
        else:
            print("\n[ABORTADO] Não foi possível transferir todos os diários (falta Chefe de Turma em algumas turmas).")
            print("O usuário 610 NÃO foi deletado para evitar perda de dados.")
            db.session.rollback()

if __name__ == "__main__":
    transferir_para_chefe_e_deletar()