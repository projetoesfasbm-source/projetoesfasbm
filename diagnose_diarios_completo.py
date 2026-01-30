# diagnose_diarios_completo.py
import os
import sys

# Adiciona o diretório atual ao path para encontrar o backend
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
from backend.models.diario_classe import DiarioClasse
from backend.models.horario import Horario
from backend.models.turma import Turma
from backend.models.school import School
from backend.models.user import User
from backend.models.aluno import Aluno
from backend.models.turma_cargo import TurmaCargo
from backend.models.instrutor import Instrutor

app = create_app()

def diagnosticar_sistema():
    with app.app_context():
        print("="*80)
        print("DIAGNÓSTICO DE INTEGRIDADE DE DIÁRIOS E VÍNCULOS (VERSÃO FINAL)")
        print("="*80)

        escolas = db.session.execute(db.select(School)).scalars().all()
        
        for escola in escolas:
            # No seu model School, o campo é 'nome'
            print(f"\n>>> UNIDADE: {escola.nome} (ID: {escola.id})")
            
            turmas = db.session.execute(db.select(Turma).filter_by(school_id=escola.id)).scalars().all()
            
            for turma in turmas:
                # No seu model Turma, o campo é 'nome'
                print(f"  Turma: {turma.nome} (ID: {turma.id})")
                
                # 1. Verificar Chefe de Turma (User -> Aluno -> TurmaCargo)
                stmt_chefe = (
                    db.select(User)
                    .join(Aluno, Aluno.user_id == User.id)
                    .join(TurmaCargo, TurmaCargo.aluno_id == Aluno.id)
                    .filter(TurmaCargo.turma_id == turma.id, TurmaCargo.cargo_nome == 'chefe_turma')
                )
                chefe = db.session.execute(stmt_chefe).scalar_one_or_none()
                status_chefe = f"OK ({chefe.nome_de_guerra})" if chefe else "SEM CHEFE DEFINIDO"
                print(f"    - Status Chefe: {status_chefe}")

                # 2. Analisar Diários (Últimos 5 desta turma)
                diarios = db.session.execute(
                    db.select(DiarioClasse).filter_by(turma_id=turma.id).order_by(DiarioClasse.id.desc()).limit(5)
                ).scalars().all()

                if not diarios:
                    print("    - Diários: Nenhum registro encontrado.")
                    continue

                for diario in diarios:
                    print(f"    [Diário ID: {diario.id}] Data: {diario.data_aula} | Status: {diario.status}")
                    
                    horario = db.session.get(Horario, diario.horario_id)
                    if not horario:
                        print("      !!! ALERTA: Diário sem vínculo com Quadro de Horários.")
                        continue

                    # IDs dos instrutores registrados no momento da criação do horário
                    id_inst1 = horario.instrutor_id
                    id_inst2 = getattr(horario, 'instrutor_id_2', None)
                    
                    # 3. Validar Instrutores e seus Vínculos de Escola (UserSchool)
                    for label, inst_id in [("Titular", id_inst1), ("Auxiliar", id_inst2)]:
                        if not inst_id:
                            print(f"      - {label}: Vazio")
                            continue
                        
                        inst_obj = db.session.get(Instrutor, inst_id)
                        if not inst_obj or not inst_obj.user:
                            print(f"      !!! ERRO: ID de Instrutor {inst_id} no horário é inválido.")
                            continue
                        
                        u = inst_obj.user
                        # Verifica se o instrutor possui o school_id na tabela user_schools
                        tem_vinculo_escola = any(int(us.school_id) == int(escola.id) for us in u.user_schools)
                        
                        msg_vinculo = "VÍNCULO OK" if tem_vinculo_escola else "!!! SEM VÍNCULO TÉCNICO COM ESTA ESCOLA !!!"
                        print(f"      - {label}: {u.nome_de_guerra} (ID Func: {u.matricula}) | {msg_vinculo}")

        print("\n" + "="*80)
        print("FIM DO DIAGNÓSTICO")
        print("="*80)

if __name__ == "__main__":
    diagnosticar_sistema()