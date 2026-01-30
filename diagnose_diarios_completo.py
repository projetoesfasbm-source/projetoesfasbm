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
        print("DIAGNÓSTICO DE INTEGRIDADE DE DIÁRIOS E VÍNCULOS (VERSÃO REVISADA)")
        print("="*80)

        escolas = db.session.execute(db.select(School)).scalars().all()
        
        for escola in escolas:
            print(f"\n>>> UNIDADE: {escola.nome} (ID: {escola.id})")
            
            turmas = db.session.execute(db.select(Turma).filter_by(school_id=escola.id)).scalars().all()
            
            for turma in turmas:
                print(f"  Turma: {turma.nome} (ID: {turma.id})")
                
                # 1. Verificar Chefe de Turma
                stmt_chefe = (
                    db.select(User)
                    .join(Aluno, Aluno.user_id == User.id)
                    .join(TurmaCargo, TurmaCargo.aluno_id == Aluno.id)
                    .filter(TurmaCargo.turma_id == turma.id, TurmaCargo.cargo_nome == 'chefe_turma')
                )
                chefe = db.session.execute(stmt_chefe).scalar_one_or_none()
                print(f"    - Status Chefe: {'OK (' + chefe.nome_de_guerra + ')' if chefe else 'SEM CHEFE DEFINIDO'}")

                # 2. Analisar Diários
                diarios = db.session.execute(
                    db.select(DiarioClasse).filter_by(turma_id=turma.id).order_by(DiarioClasse.id.desc()).limit(5)
                ).scalars().all()

                for diario in diarios:
                    print(f"    [Diário ID: {diario.id}] Data: {diario.data_aula} | Status: {diario.status}")
                    
                    # Correção Crítica: O campo no seu model é id_horario
                    horario = db.session.get(Horario, diario.id_horario)
                    if not horario:
                        print("      !!! ALERTA: Diário sem vínculo com Quadro de Horários.")
                        continue

                    # IDs dos instrutores no horário conforme seu model Horario
                    id_inst1 = horario.instrutor_id
                    id_inst2 = getattr(horario, 'id_instrutor_auxiliar', None)
                    
                    for label, inst_id in [("Titular", id_inst1), ("Auxiliar", id_inst2)]:
                        if not inst_id:
                            print(f"      - {label}: Vazio")
                            continue
                        
                        inst_obj = db.session.get(Instrutor, inst_id)
                        if not inst_obj or not inst_obj.user:
                            print(f"      !!! ERRO: Instrutor ID {inst_id} inválido.")
                            continue
                        
                        u = inst_obj.user
                        tem_vinculo = any(int(us.school_id) == int(escola.id) for us in u.user_schools)
                        
                        msg_status = "VÍNCULO OK" if tem_vinculo else "!!! SEM VÍNCULO COM ESTA ESCOLA !!!"
                        print(f"      - {label}: {u.nome_de_guerra} ({u.matricula}) | {msg_status}")

        print("\n" + "="*80)
        print("FIM DO DIAGNÓSTICO")
        print("="*80)

if __name__ == "__main__":
    diagnosticar_sistema()