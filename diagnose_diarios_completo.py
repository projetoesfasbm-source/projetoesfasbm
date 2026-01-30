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
from backend.models.user_school import UserSchool

app = create_app()

def diagnosticar_sistema():
    with app.app_context():
        print("="*80)
        print("DIAGNÓSTICO DE INTEGRIDADE DE DIÁRIOS E VÍNCULOS (VERSÃO FINAL CORRIGIDA)")
        print("="*80)

        escolas = db.session.execute(db.select(School)).scalars().all()
        
        for escola in escolas:
            print(f"\n>>> UNIDADE: {escola.nome} (ID: {escola.id})")
            
            turmas = db.session.execute(db.select(Turma).filter_by(school_id=escola.id)).scalars().all()
            
            for turma in turmas:
                print(f"\n  Turma: {turma.nome} (ID: {turma.id})")
                
                # 1. Verificar Chefe de Turma (Cargos definidos em TurmaCargo)
                stmt_chefe = (
                    db.select(User)
                    .join(Aluno, Aluno.user_id == User.id)
                    .join(TurmaCargo, TurmaCargo.aluno_id == Aluno.id)
                    .filter(TurmaCargo.turma_id == turma.id, TurmaCargo.cargo_nome == 'chefe_turma')
                )
                chefe = db.session.execute(stmt_chefe).scalar_one_or_none()
                status_chefe = f"OK ({chefe.nome_de_guerra})" if chefe else "!!! SEM CHEFE DEFINIDO !!!"
                print(f"    - Status Chefe: {status_chefe}")

                # 2. Analisar Diários recentes
                diarios = db.session.execute(
                    db.select(DiarioClasse).filter_by(turma_id=turma.id).order_by(DiarioClasse.id.desc()).limit(5)
                ).scalars().all()

                if not diarios:
                    print("      (Nenhum diário encontrado para esta turma)")

                for diario in diarios:
                    print(f"    [Diário ID: {diario.id}] Data: {diario.data_aula} | Status: {diario.status}")
                    
                    # Correção do erro de atributo: horario_id é o padrão no banco
                    hid = getattr(diario, 'horario_id', None)
                    horario = db.session.get(Horario, hid) if hid else None
                    
                    if not horario:
                        print("      !!! ALERTA: Diário sem vínculo válido com Quadro de Horários.")
                        continue

                    # Conforme o modelo Horario, os campos são instrutor_id e instrutor_id_2
                    id_inst1 = horario.instrutor_id
                    id_inst2 = horario.instrutor_id_2 # Segundo instrutor conforme migrate ff67dccfc78a
                    
                    for label, inst_id in [("Titular", id_inst1), ("Auxiliar", id_inst2)]:
                        if not inst_id:
                            print(f"      - {label}: Vazio no Horário")
                            continue
                        
                        inst_obj = db.session.get(Instrutor, inst_id)
                        if not inst_obj or not inst_obj.user:
                            print(f"      !!! ERRO: Instrutor ID {inst_id} não possui perfil de usuário.")
                            continue
                        
                        u = inst_obj.user
                        # Verifica se o instrutor tem entrada na tabela user_schools para esta escola específica
                        # Isso é vital pois o User.get_role_in_school(school_id) agora isola os contextos
                        vinculo_escola = db.session.execute(
                            db.select(UserSchool).filter_by(user_id=u.id, school_id=escola.id)
                        ).scalar_one_or_none()
                        
                        if vinculo_escola:
                            print(f"      - {label}: {u.nome_de_guerra} ({u.matricula}) | VÍNCULO OK (Role: {vinculo_escola.role})")
                        else:
                            print(f"      - {label}: {u.nome_de_guerra} ({u.matricula}) | !!! SEM VÍNCULO COM ESTA UNIDADE !!!")
                            print(f"        (Isso impede que ele veja diários desta escola)")

        print("\n" + "="*80)
        print("FIM DO DIAGNÓSTICO")
        print("="*80)

if __name__ == "__main__":
    diagnosticar_sistema()