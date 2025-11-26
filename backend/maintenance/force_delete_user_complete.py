# backend/maintenance/force_delete_user_complete.py
import sys
import os
from sqlalchemy import select, delete

# Adiciona o diretório raiz ao path para importar os módulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from backend.app import create_app
from backend.models.database import db
from backend.models.user import User
from backend.models.processo_disciplina import ProcessoDisciplina
from backend.models.resposta import Resposta
from backend.models.site_config import SiteConfig

def force_delete_user(matricula):
    app = create_app()
    with app.app_context():
        # 1. Localizar o usuário
        user = db.session.scalar(select(User).where(User.matricula == matricula))
        if not user:
            print(f"Usuário com matrícula {matricula} não encontrado.")
            return

        print(f"Iniciando exclusão forçada para: {user.nome_completo} (ID: {user.id}, Matrícula: {user.matricula})")

        # 2. Remover ou desvincular dependências que não têm cascade automático

        # A) Processos Disciplinares onde é Relator (Não podemos apagar o processo, vamos definir um 'relator fantasma' ou nulo se permitido, ou deletar se for teste)
        # Nota: relator_id é nullable=False. Se tiver processos, é ideal reatribuir ou deletar o processo.
        # AQUI: Vamos deletar os processos para garantir a limpeza (cuidado em produção) ou alertar.
        processos = db.session.scalars(select(ProcessoDisciplina).where(ProcessoDisciplina.relator_id == user.id)).all()
        if processos:
            print(f" -> Encontrados {len(processos)} processos onde o usuário é Relator. Excluindo processos...")
            for p in processos:
                db.session.delete(p)
        
        # B) Respostas de Questionários
        respostas = db.session.scalars(select(Resposta).where(Resposta.user_id == user.id)).all()
        if respostas:
            print(f" -> Encontradas {len(respostas)} respostas de questionários. Excluindo...")
            for r in respostas:
                db.session.delete(r)

        # C) Site Configs (Setar updated_by para Null)
        configs = db.session.scalars(select(SiteConfig).where(SiteConfig.updated_by == user.id)).all()
        if configs:
            print(f" -> Encontradas {len(configs)} configurações editadas pelo usuário. Desvinculando...")
            for c in configs:
                c.updated_by = None

        # 3. Excluir o usuário (O cascade do SQLAlchemy cuidará de Aluno, Instrutor, UserSchool, Notificações)
        try:
            db.session.delete(user)
            db.session.commit()
            print("✅ Usuário excluído com sucesso!")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao excluir usuário final: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python -m backend.maintenance.force_delete_user_complete <MATRICULA>")
    else:
        force_delete_user(sys.argv[1])