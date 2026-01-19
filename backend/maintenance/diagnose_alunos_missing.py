import sys
import os
from sqlalchemy import text

# Configuração de caminho
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from backend.app import create_app
from backend.models.database import db
from backend.models.school import School
from backend.models.user import User
from backend.models.aluno import Aluno
from backend.models.user_school import UserSchool
from backend.models.turma import Turma

app = create_app()

def diagnosticar_escola():
    with app.app_context():
        # Nome exato fornecido
        NOME_ESCOLA = "Centro de Treinamento e Especialização de Montenegro - CTEMn - CBFPM"
        
        print(f"\n=== DIAGNÓSTICO DE ALUNOS: {NOME_ESCOLA} ===")
        
        # 1. Encontrar a Escola e seu ID
        escola = School.query.filter_by(nome=NOME_ESCOLA).first()
        if not escola:
            # Tenta busca parcial se falhar
            escola = School.query.filter(School.nome.like("%Montenegro%")).first()
            
        if not escola:
            print("ERRO CRÍTICO: Escola não encontrada no banco de dados.")
            return

        print(f"Escola Encontrada: ID {escola.id} | Nome: {escola.nome}")
        
        # 2. Verificar quantos vínculos existem na tabela de ligação (UserSchool)
        count_users = UserSchool.query.filter_by(school_id=escola.id).count()
        print(f"Total de Usuários vinculados a esta escola (UserSchool): {count_users}")
        
        # 3. Listar Alunos que DEVERIAM estar lá (com base em turmas da escola)
        print("\n--- Verificando Alunos via Turmas desta Escola ---")
        turmas = Turma.query.filter_by(school_id=escola.id).all()
        ids_turmas = [t.id for t in turmas]
        
        if not turmas:
            print("ALERTA: Esta escola não possui nenhuma turma cadastrada.")
        else:
            print(f"Turmas encontradas: {[t.nome for t in turmas]} (IDs: {ids_turmas})")
            
            alunos_nas_turmas = Aluno.query.filter(Aluno.turma_id.in_(ids_turmas)).all()
            print(f"Alunos encontrados vinculados a estas turmas: {len(alunos_nas_turmas)}")
            
            for al in alunos_nas_turmas:
                user = al.user
                # Verifica se o usuario tem o vinculo de escola
                vinculo = UserSchool.query.filter_by(user_id=user.id, school_id=escola.id).first()
                status_vinculo = "OK" if vinculo else "ERRO (Sem UserSchool)"
                print(f" - Aluno: {user.nome_completo} | Turma: {al.turma.nome} | Vínculo Escola: {status_vinculo}")

        # 4. Verificar Alunos "Perdidos" (Criados recentemente mas sem vínculo escolar)
        print("\n--- Procurando Alunos 'Perdidos' (Sem vínculo de escola) ---")
        # Busca usuários criados recentemente que tenham perfil de aluno mas NENHUMA escola vinculada
        # ou usuários que estão vinculados à escola 'errada' mas com nome sugerindo essa
        
        # Estratégia: Buscar alunos sem UserSchool
        sql_orrfos = text("""
            SELECT u.id, u.nome_completo, u.email 
            FROM users u
            JOIN alunos a ON a.user_id = u.id
            LEFT JOIN user_schools us ON us.user_id = u.id
            WHERE us.school_id IS NULL
        """)
        orfaos = db.session.execute(sql_orrfos).fetchall()
        
        if orfaos:
            print(f"ALERTA: Existem {len(orfaos)} alunos no sistema SEM NENHUMA ESCOLA vinculada:")
            for o in orfaos:
                print(f" - ID: {o.id} | Nome: {o.nome_completo}")
        else:
            print("Não foram encontrados alunos totalmente órfãos de escola.")

if __name__ == "__main__":
    diagnosticar_escola()