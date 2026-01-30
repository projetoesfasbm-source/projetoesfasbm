# diagnosticar_filtros_instrutor.py
import os
import sys

# Adiciona o diretório atual ao path
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
from backend.models.diario_classe import DiarioClasse
from backend.models.horario import Horario
from backend.models.turma import Turma
from backend.models.instrutor import Instrutor
from backend.models.user import User
from backend.models.user_school import UserSchool

app = create_app()

def verificar_visibilidade():
    with app.app_context():
        print("="*80)
        print("DIAGNÓSTICO DE FILTRAGEM E PERMISSÕES DE INSTRUTOR")
        print("="*80)

        # 1. Localize o Diário específico (ex: ID 2944 que Sarti/Pacheco não veem)
        diario_id = 2944 # <--- Altere para o ID do diário problemático
        diario = db.session.get(DiarioClasse, diario_id)
        
        if not diario:
            print(f"[!] Diário {diario_id} não encontrado.")
            return

        turma = diario.turma
        escola_id = turma.school_id
        print(f"Analisando Diário: {diario.id} | Turma: {turma.nome} | Unidade ID: {escola_id}")

        # 2. Localizar o Horário que você confirmou que existe
        # Buscamos exatamente como o sistema faz na query de listar diários
        dias_map = {0: 'Segunda-feira', 1: 'Terça-feira', 2: 'Quarta-feira', 
                    3: 'Quinta-feira', 4: 'Sexta-feira', 5: 'Sábado', 6: 'Domingo'}
        dia_texto = dias_map[diario.data_aula.weekday()]

        horarios = db.session.execute(
            db.select(Horario).filter_by(
                pelotao=turma.nome,
                dia_semana=dia_texto,
                periodo=diario.periodo,
                disciplina_id=diario.disciplina_id
            )
        ).scalars().all()

        if not horarios:
            print("[!] ERRO: O script não encontrou o Horário no banco usando os filtros automáticos.")
            print(f"    Filtros: Pelotão='{turma.nome}', Dia='{dia_texto}', Período={diario.periodo}")
            return

        for h in horarios:
            print(f"\n[OK] Horário encontrado (ID: {h.id})")
            
            # 3. Verificar os Instrutores vinculados a este Horário
            for label, inst_id in [("Titular", h.instrutor_id), ("Auxiliar", h.instrutor_id_2)]:
                if not inst_id:
                    print(f"  - {label}: (Vazio)")
                    continue
                
                inst_obj = db.session.get(Instrutor, inst_id)
                u = inst_obj.user if inst_obj else None
                
                if not u:
                    print(f"  - {label}: Perfil de Instrutor {inst_id} sem usuário vinculado!")
                    continue

                print(f"  - {label}: {u.nome_de_guerra} (Matrícula: {u.matricula})")
                
                # --- VERIFICAÇÃO CRÍTICA DE VÍNCULO ESCOLAR ---
                # O seu modelo User.get_role_in_school(school_id) exige este vínculo
                vinculo = db.session.execute(
                    db.select(UserSchool).filter_by(user_id=u.id, school_id=escola_id)
                ).scalar_one_or_none()

                if vinculo:
                    print(f"    [OK] Vínculo com a Unidade {escola_id} confirmado (Papel: {vinculo.role})")
                else:
                    print(f"    [!!!] BLOQUEIO: O instrutor NÃO possui vínculo na tabela 'user_schools' para esta Unidade.")
                    print(f"    [!] MOTIVO: Sem esse registro, o sistema retorna 'None' para as permissões dele nesta escola.")

                # Verificar se o usuário está ativo
                if not u.is_active:
                    print(f"    [!!!] BLOQUEIO: O usuário está com 'is_active=False'.")

        print("\n" + "="*80)
        print("FIM DO DIAGNÓSTICO")
        print("="*80)

if __name__ == "__main__":
    verificar_visibilidade()