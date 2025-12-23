import sys
import os

# Adiciona o diretório atual ao path
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.database import db
from backend.models.turma import Turma
from backend.models.disciplina import Disciplina
from backend.models.diario_classe import DiarioClasse

app = create_app()

def diagnosticar_adm():
    with app.app_context():
        print("\n" + "="*80)
        print("RASTREAMENTO: ADMINISTRAÇÃO PÚBLICA (TURMA 8)")
        print("="*80)
        
        # 1. Localiza a Turma 8
        turma = db.session.query(Turma).filter(Turma.nome.like('%8%')).first()
        if not turma:
            print("ERRO: Turma 8 não encontrada.")
            return

        print(f"Turma Alvo: {turma.nome}")

        # 2. Busca disciplinas com nomes parecidos
        # Usamos 'Operações' e 'Administração' para garantir que pegamos a certa
        termos = ['Administração', 'Operações']
        disciplinas_ids = set()
        
        for termo in termos:
            res = db.session.query(Disciplina).filter(Disciplina.materia.like(f'%{termo}%')).all()
            for d in res:
                disciplinas_ids.add(d.id)

        encontrou = False

        for disc_id in disciplinas_ids:
            disc = db.session.get(Disciplina, disc_id)
            
            # Busca os diários dessa disciplina na Turma 8
            diarios = db.session.query(DiarioClasse).filter_by(
                turma_id=turma.id, 
                disciplina_id=disc.id
            ).order_by(DiarioClasse.data_aula, DiarioClasse.periodo, DiarioClasse.id).all()

            count = len(diarios)
            
            # Só mostra se tiver mais registros que o normal ou se for a de 29 tempos
            if count > 0:
                encontrou = True
                print(f"\n>>> DISCIPLINA: {disc.materia} (ID: {disc.id})")
                print(f"Registros: {count} | Carga Prevista: {disc.carga_horaria_prevista}h")
                
                if count > disc.carga_horaria_prevista:
                    print("(!) ATENÇÃO: Contém mais registros que a carga horária prevista.")

                print(f"{'ID':<6} | {'DATA':<12} | {'PERIODO':<8} | {'REGISTRADO POR'}")
                print("-" * 65)
                
                chaves_vistas = set()
                
                for d in diarios:
                    dt = d.data_aula.strftime('%d/%m/%Y')
                    per = str(d.periodo) if d.periodo is not None else "NULL"
                    
                    # Quem registrou (provavelmente Boer novamente)
                    quem = "---"
                    if d.responsavel:
                        quem = d.responsavel.nome_de_guerra or d.responsavel.nome_completo

                    # Lógica para detectar duplicata visualmente
                    chave = f"{dt}-{per}"
                    aviso = ""
                    
                    # Se já vimos esta data+periodo nesta iteração, é duplicata
                    if chave in chaves_vistas and per != "NULL":
                        aviso = " <--- DUPLICADO! APAGUE ESTE ID"
                    
                    # Se o periodo for NULL, verificamos se tem muitos no mesmo dia
                    # (Lógica simplificada: mostra duplicado se data repetir muito, mas o aviso acima é mais preciso para os novos)
                    
                    chaves_vistas.add(chave)

                    print(f"{d.id:<6} | {dt:<12} | {per:<8} | {quem}{aviso}")

        if not encontrou:
            print("\nNenhum registro encontrado para estes termos na Turma 8.")

if __name__ == "__main__":
    diagnosticar_adm()