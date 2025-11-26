# backend/maintenance/force_delete_by_id.py
import sys
import os
from sqlalchemy import select

# Ajusta o caminho para encontrar a aplicação
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from backend.app import create_app
from backend.models.database import db
from backend.models.user import User
from backend.models.processo_disciplina import ProcessoDisciplina
from backend.models.resposta import Resposta
from backend.models.site_config import SiteConfig

def force_delete_by_id(user_id):
    app = create_app()
    with app.app_context():
        # 1. Busca pelo ID numérico
        user = db.session.get(User, int(user_id))
        if not user:
            print(f"ERRO: Usuário com ID {user_id} não encontrado no banco.")
            return

        print(f"--- Iniciando exclusão do usuário: {user.nome_completo} (ID: {user.id} | Matrícula: {user.matricula}) ---")

        # 2. Remover dependências que bloqueiam a exclusão (Foreign Keys sem cascade)
        
        # A) Processos onde é Relator
        processos = db.session.scalars(select(ProcessoDisciplina).where(ProcessoDisciplina.relator_id == user.id)).all()
        if processos:
            print(f" -> Removendo {len(processos)} processos disciplinares onde é relator...")
            for p in processos:
                db.session.delete(p)

        # B) Respostas de questionários
        respostas = db.session.scalars(select(Resposta).where(Resposta.user_id == user.id)).all()
        if respostas:
            print(f" -> Removendo {len(respostas)} respostas de questionários...")
            for r in respostas:
                db.session.delete(r)

        # C) Configurações do site (desvincular autoria, setar NULL)
        configs = db.session.scalars(select(SiteConfig).where(SiteConfig.updated_by == user.id)).all()
        if configs:
            print(f" -> Desvinculando {len(configs)} configurações de site...")
            for c in configs:
                c.updated_by = None

        # 3. Excluir o Usuário (Cascade cuidará de Aluno, Instrutor, etc.)
        try:
            db.session.delete(user)
            db.session.commit()
            print("✅ Usuário excluído com sucesso!\n")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro crítico ao excluir: {e}\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python -m backend.maintenance.force_delete_by_id <ID_NUMERICO>")
    else:
        force_delete_by_id(sys.argv[1])