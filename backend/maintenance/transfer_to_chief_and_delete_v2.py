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
from backend.models.turma_cargo import TurmaCargo
from backend.models.frequencia import FrequenciaAluno  # IMPORTANTE: Importar modelo de Frequência

app = create_app()

def transferir_para_chefe_e_deletar():
    with app.app_context():
        BAD_ID = 610
        ROLE_CHEFE_NAME = "Chefe de Turma"
        
        print(f"\n=== TRANSFERÊNCIA E REMOÇÃO COMPLETA: ID {BAD_ID} ===")
        
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
            print(f"\n[!] Existem {len(diarios)} diários assinados por este usuário. Processando transferências...")
            
            for diario in diarios:
                turma = diario.turma
                if not turma:
                    print(f"    [ERRO] Diário ID {diario.id} sem turma. Pulo.")
                    continue

                # Busca Chefe
                cargo_chefe = TurmaCargo.query.filter_by(turma_id=turma.id, cargo_nome=ROLE_CHEFE_NAME).first()
                chefe_real = None
                
                if cargo_chefe:
                    aluno_chefe = db.session.get(Aluno, cargo_chefe.aluno_id)
                    if aluno_chefe and aluno_chefe.user_id != BAD_ID:
                        chefe_real = aluno_chefe.user
                
                if chefe_real:
                    print(f"    -> Diário {diario.id}: Transferindo para {chefe_real.nome_completo}")
                    diario.responsavel_id = chefe_real.id
                    obs = diario.observacoes or ""
                    if "[Autoria transferida" not in obs:
                        diario.observacoes = f"{obs} [Transf. ID {BAD_ID} para Chefe]"
                else:
                    print(f"    [FALHA] Turma '{turma.nome}' sem Chefe definido. Impossível transferir.")
                    todos_transferidos = False
        else:
            print("\n[OK] Nenhum diário pendente (ou já foram transferidos).")

        # 3. Só deleta se a parte dos diários estiver OK
        if todos_transferidos:
            try:
                print("\n[OK] Diários resolvidos. Iniciando limpeza profunda...")
                
                # A. LIMPEZA DE FREQUÊNCIAS (A Causa do Erro Anterior)
                aluno_profile = Aluno.query.filter_by(user_id=BAD_ID).first()
                if aluno_profile:
                    print(f" - Apagando registros de Frequência (Chamada)...")
                    # Deleta todas as presenças/faltas vinculadas a este aluno
                    db.session.query(FrequenciaAluno).filter_by(aluno_id=aluno_profile.id).delete()
                    
                    # B. LIMPEZA DE CARGOS
                    print(" - Apagando Cargos de Turma (se houver)...")
                    TurmaCargo.query.filter_by(aluno_id=aluno_profile.id).delete()
                    
                    # C. REMOVE PERFIL DE ALUNO
                    print(" - Apagando Perfil de Aluno...")
                    db.session.delete(aluno_profile)
                
                # D. REMOVE VÍNCULOS DE ESCOLA
                print(" - Apagando Vínculos Escolares (UserSchool)...")
                UserSchool.query.filter_by(user_id=BAD_ID).delete()
                
                # E. REMOVE O USUÁRIO
                print(f" - Apagando Usuário Mestre ID {BAD_ID}...")
                db.session.delete(bad_user)

                db.session.commit()
                print(f"\nSUCESSO TOTAL: Usuário {BAD_ID} foi removido do sistema.")
                
            except Exception as e:
                db.session.rollback()
                print(f"Erro Fatal ao deletar: {str(e)}")
        else:
            print("\n[ABORTADO] Resolva os Chefes de Turma antes de tentar novamente.")
            db.session.rollback()

if __name__ == "__main__":
    transferir_para_chefe_e_deletar()