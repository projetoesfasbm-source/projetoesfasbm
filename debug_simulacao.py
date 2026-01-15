from backend.app import create_app
from backend.models.database import db
from backend.services.justica_service import JusticaService
from backend.models.school import School
from backend.models.user import User
from backend.models.discipline_rule import DisciplineRule
from backend.models.processo_disciplina import StatusProcesso
from flask import g
import sys

app = create_app()

with app.app_context():
    print("="*60)
    print("SIMULAÇÃO DO CONTROLLER DE JUSTIÇA")
    print("="*60)

    try:
        # 1. Tentar pegar uma escola ativa para teste
        school = db.session.query(School).first()
        if not school:
            print("[AVISO] Nenhuma escola encontrada no banco.")
            sys.exit(0)
        
        print(f"1. Escola selecionada: {school.nome} (ID: {school.id})")
        # Verifica se o campo existe e seu valor
        val_type = getattr(school, 'npccal_type', 'CAMPO_INEXISTENTE')
        print(f"   Tipo de Pontuação (npccal_type): {val_type!r}")
        
        # Simula o objeto global 'g' que o controller usa
        g.active_school = school

        # 2. Tentar pegar um usuário (simulando o usuário logado)
        user = db.session.query(User).first()
        if not user:
             print("[ERRO] Nenhum usuário encontrado para teste.")
             sys.exit(1)
        print(f"2. Usuário simulado: {user.nome_completo} (ID: {user.id})")

        # 3. Testar a busca de processos (JusticaService)
        print("\n3. Testando busca de processos...")
        try:
            processos = JusticaService.get_processos_para_usuario(user, school_id_override=school.id)
            print(f"   [SUCESSO] {len(processos)} processos retornados.")
            
            # Testa a linha exata que filtra status no controller
            print("   Testando filtro de status (Enum)...")
            em_andamento = [p for p in processos if str(p.status) != StatusProcesso.FINALIZADO.value]
            print(f"   [SUCESSO] Filtro OK. Em andamento: {len(em_andamento)}")
            
        except Exception as e:
            print(f"   [FALHA] Erro ao buscar/processar processos: {e}")
            import traceback
            traceback.print_exc()

        # 4. Testar busca de Regras (Onde suspeitamos do erro)
        print("\n4. Testando busca de Regras de Disciplina...")
        try:
            if val_type == 'CAMPO_INEXISTENTE':
                print("   [PULAR] Campo npccal_type não existe no modelo School.")
            else:
                regras = db.session.query(DisciplineRule).filter(
                    DisciplineRule.npccal_type == school.npccal_type
                ).order_by(DisciplineRule.codigo).all()
                print(f"   [SUCESSO] {len(regras)} regras encontradas para o tipo '{school.npccal_type}'.")
        except Exception as e:
            print(f"   [FALHA] Erro ao buscar regras: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"\n[CRÍTICO] Erro geral na simulação: {e}")
        import traceback
        traceback.print_exc()
    
    print("="*60)