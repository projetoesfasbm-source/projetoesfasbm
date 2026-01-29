# backend/maintenance/fix_duplicidade_alunos.py
import sys
import os

# Adiciona o diretório raiz ao path para importar os módulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from backend.app import create_app
from backend.models.database import db
from backend.models.user import User
from backend.models.user_school import UserSchool
from backend.models.turma import Turma
from sqlalchemy import select

app = create_app()

def corrigir_alunos_duplicados():
    with app.app_context():
        print("--- INICIANDO CORREÇÃO DE VÍNCULOS DUPLICADOS (ALUNOS) ---")
        
        # Busca todos os usuários com papel 'aluno'
        alunos = db.session.scalars(select(User).where(User.role == 'aluno')).all()
        
        corrigidos = 0
        sem_turma = 0
        
        for user in alunos:
            # Verifica quantos vínculos de escola esse aluno tem
            vinculos = user.user_schools
            
            if len(vinculos) > 1:
                print(f"\nAluno encontrado com múltiplas escolas: {user.nome_completo} ({user.matricula})")
                print(f"   -> Vínculos atuais: {[v.school_id for v in vinculos]}")
                
                # Tenta descobrir a escola REAL através da Turma
                profile = user.aluno_profile
                if profile and profile.turma_id:
                    turma = db.session.get(Turma, profile.turma_id)
                    if turma:
                        school_id_correto = turma.school_id
                        print(f"   -> Escola Correta identificada pela Turma: ID {school_id_correto} ({turma.nome})")
                        
                        # REMOVE OS VÍNCULOS ERRADOS
                        for v in vinculos:
                            if v.school_id != school_id_correto:
                                print(f"      [X] Removendo vínculo fantasma com Escola ID {v.school_id}...")
                                db.session.delete(v)
                        
                        corrigidos += 1
                    else:
                        print("   -> ERRO: Turma vinculada não encontrada no banco.")
                else:
                    print("   -> ATENÇÃO: Aluno sem turma vinculada. Não é possível determinar a escola correta automaticamente.")
                    sem_turma += 1
        
        if corrigidos > 0:
            db.session.commit()
            print(f"\n--- SUCESSO: {corrigidos} alunos foram corrigidos e agora pertencem apenas à sua escola real. ---")
        else:
            print("\n--- Nenhum aluno com turma precisou de correção. ---")
            
        if sem_turma > 0:
            print(f"--- AVISO: {sem_turma} alunos com múltiplos vínculos não têm turma definida e foram ignorados. ---")

if __name__ == "__main__":
    corrigir_alunos_duplicados()