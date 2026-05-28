import sys
sys.path.insert(0, '.')
from backend.app import create_app
from backend.models.database import db
from backend.models.edicao import Edicao
from backend.models.school import School
from backend.models.turma import Turma
from backend.models.aluno import Aluno
from backend.models.ciclo import Ciclo
from backend.models.processo_disciplina import ProcessoDisciplina
from backend.models.disciplina import Disciplina

def run_correcoes():
    app = create_app()
    with app.app_context():
        print("=== INICIANDO TRANSFERÊNCIA DE DADOS PARA O NOVO MODELO (EDIÇÕES) ===")
        schools = School.query.all()
        for s in schools:
            # Pega a primeira edição da escola (ou cria se não existir)
            ed = Edicao.query.filter_by(school_id=s.id).order_by(Edicao.id).first()
            if not ed:
                print(f"[{s.nome}] Nenhuma edição encontrada. Criando Edição Padrão...")
                ed = Edicao(school_id=s.id, nome="Edição Padrão", ano=2026, status="Ativa", is_default=True)
                db.session.add(ed)
                db.session.commit()
            
            print(f"[{s.nome}] Usando Edição: {ed.nome} (ID: {ed.id})")

            # 1. Atualiza Turmas
            turmas = db.session.query(Turma).filter_by(school_id=s.id, edicao_id=None).all()
            for t in turmas:
                t.edicao_id = ed.id
            print(f" - {len(turmas)} Turmas atualizadas.")

            # 2. Atualiza Ciclos
            ciclos = db.session.query(Ciclo).filter_by(school_id=s.id, edicao_id=None).all()
            for c in ciclos:
                c.edicao_id = ed.id
            print(f" - {len(ciclos)} Ciclos atualizados.")

            # 3. Atualiza Alunos
            # Vincula a edição aos alunos que estão em turmas da escola
            alunos = db.session.query(Aluno).join(Turma, Aluno.turma_id == Turma.id).filter(
                Turma.school_id == s.id, Aluno.edicao_id == None
            ).all()
            for a in alunos:
                a.edicao_id = ed.id
            print(f" - {len(alunos)} Alunos atualizados.")

            db.session.commit()
            
        print("=== TRANSFERÊNCIA CONCLUÍDA COM SUCESSO! ===")

if __name__ == '__main__':
    run_correcoes()
