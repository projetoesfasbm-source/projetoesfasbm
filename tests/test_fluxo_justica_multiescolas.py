import pytest
from unittest.mock import patch
from datetime import datetime
from backend.models.database import db
from backend.models.user import User
from backend.models.aluno import Aluno
from backend.models.turma import Turma
from backend.models.school import School
from backend.models.discipline_rule import DisciplineRule
from backend.models.processo_disciplina import ProcessoDisciplina, StatusProcesso
from backend.models.user_school import UserSchool

# Fixture parametrizada que roda o setup 3 vezes (uma para cada tipo de escola)
@pytest.fixture(params=["cbfpm", "cspm", "ctsp"])
def setup_cenario_escola_tipo(request, test_app):
    # CORREÇÃO DE CONFIGURAÇÃO CSRF:
    # 1. WTF_CSRF_ENABLED = True: Garante que o campo 'csrf_token' exista no form (template não quebra).
    # 2. WTF_CSRF_CHECK_DEFAULT = False: Impede que o Flask rejeite o POST do teste por falta de token.
    test_app.config['WTF_CSRF_ENABLED'] = True
    test_app.config['WTF_CSRF_CHECK_DEFAULT'] = False

    tipo_escola = request.param
    with test_app.app_context():
        # 1. Criar Escola e Turma Configurada com o Tipo Atual
        # CORREÇÃO: Usando 'nome' em vez de 'name'
        school = School(nome=f"Escola Teste {tipo_escola.upper()}", npccal_type=tipo_escola)
        db.session.add(school)
        # Flush para garantir que school tenha ID
        db.session.flush()

        turma = Turma(nome=f"Turma {tipo_escola.upper()}", school_id=school.id, ano=str(datetime.now().year))
        db.session.add(turma)
        # Não precisa flush aqui se não formos usar turma.id imediatamente para outra FK obrigatória no mesmo bloco,
        # mas aluno_profile precisa, então vamos garantir no final.

        # 2. Criar Usuários (Admin e Aluno)
        # Admin
        admin_user = User(
            email=f"admin_{tipo_escola}@policia.rs.gov.br",
            nome_completo=f"Sgt Admin {tipo_escola.upper()}",
            role="admin_escola", # Role correta
            matricula=f"1000{tipo_escola}" 
        )
        admin_user.set_password("password123")
        admin_user.is_active = True
        db.session.add(admin_user)
        
        # CORREÇÃO CRÍTICA: Flush para gerar o ID do usuário antes de usar em UserSchool
        db.session.flush()
        
        # Vínculo explícito do Admin com a Escola (importante para o seletor funcionar)
        user_school = UserSchool(user_id=admin_user.id, school_id=school.id, role="admin_escola")
        db.session.add(user_school)
        
        # Aluno
        aluno_user = User(
            email=f"aluno_{tipo_escola}@policia.rs.gov.br",
            nome_completo=f"Sd Aluno {tipo_escola.upper()}",
            role="aluno",
            matricula=f"2000{tipo_escola}" 
        )
        aluno_user.set_password("password123")
        aluno_user.is_active = True
        db.session.add(aluno_user)
        
        # CORREÇÃO CRÍTICA: Flush para gerar o ID do aluno antes de usar em UserSchool e Aluno profile
        db.session.flush()
        
        # Vínculo explícito do Aluno com a Escola
        user_school_aluno = UserSchool(user_id=aluno_user.id, school_id=school.id, role="aluno")
        db.session.add(user_school_aluno)

        # Perfil do Aluno vinculado à Turma
        # CORREÇÃO CRÍTICA: 
        # 1. Removido 'numero' e 'nome_guerra' (não existem no model)
        # 2. Adicionado 'opm' (obrigatório)
        aluno_profile = Aluno(
            user_id=aluno_user.id, 
            turma_id=turma.id, 
            opm="1º BPM" 
        )
        db.session.add(aluno_profile)
        
        # 3. Criar Regra Disciplinar Específica para o Tipo
        regra = DisciplineRule(
            npccal_type=tipo_escola,
            codigo="101",
            descricao=f"Infração Genérica {tipo_escola.upper()}",
            pontos=1.5
        )
        db.session.add(regra)
        
        # Commit final de tudo
        db.session.commit()

        yield {
            'tipo': tipo_escola,
            'school': school,
            'turma': turma,
            'admin': admin_user,
            'aluno_user': aluno_user,
            'aluno_profile': aluno_profile,
            'regra': regra
        }

def test_fluxo_completo_justica_todas_escolas(test_client, test_app, setup_cenario_escola_tipo):
    """
    Testa o ciclo de vida completo de um processo disciplinar para CBFPM, CSPM e CTSP.
    """
    dados = setup_cenario_escola_tipo
    tipo_escola = dados['tipo']
    school_id = dados['school'].id
    
    admin_email = dados['admin'].email
    aluno_email = dados['aluno_user'].email
    aluno_id = dados['aluno_profile'].id
    regra_id = dados['regra'].id

    print(f"\n>>> INICIANDO VALIDAÇÃO DE FLUXO PARA: {tipo_escola.upper()} <<<")

    # Mock do envio de e-mail (função solta, não método de classe)
    with patch('backend.services.email_service.send_async_email_brevo') as mock_email:
        # O mock retorna None por padrão, suficiente para simular sucesso
        
        # =================================================================================
        # 1. CRIAÇÃO DA INFRAÇÃO (ADMIN)
        # =================================================================================
        # Tenta logar.
        # CORREÇÃO DE ROTA: A rota é /login, não /auth/login (verificado no auth_controller.py)
        login_resp = test_client.post('/login', data={'email': admin_email, 'password': 'password123'}, follow_redirects=True)
        assert login_resp.status_code == 200
        
        # FLUXO DE SELEÇÃO DE ESCOLA (ESSENCIAL):
        # Se o sistema detecta múltiplas escolas ou exige seleção, ele redireciona para /select_school.
        # Devemos fazer o POST simulando a escolha da escola criada no teste.
        test_client.post('/select_school', data={'school_id': school_id}, follow_redirects=True)

        data_fato = datetime.now().strftime('%Y-%m-%d')
        payload_criacao = {
            'tipo_registro': 'infracao',
            'alunos_selecionados': [aluno_id],
            'data_fato': data_fato,
            'hora_fato': '10:00',
            'descricao': f'Fato disciplinar ocorrido na escola {tipo_escola}.',
            'regra_id': regra_id,
            'observacao': 'Observação inicial do admin.',
            'origem_punicao': 'NPCCAL',
            'is_crime': 'false'
        }

        resp_create = test_client.post('/justica-e-disciplina/registrar-em-massa', data=payload_criacao, follow_redirects=True)
        
        # Debug se falhar: imprime o título da página retornada para entender onde parou
        if b"sucesso" not in resp_create.data and b"registros criados" not in resp_create.data:
            print(f"ERRO NA CRIAÇÃO. Conteúdo retornado: {resp_create.data.decode('utf-8')[:500]}")

        assert resp_create.status_code == 200
        assert b"sucesso" in resp_create.data or b"registros criados" in resp_create.data

        # Verificar persistência no banco
        with test_app.app_context():
            processo = db.session.query(ProcessoDisciplina).filter_by(aluno_id=aluno_id).first()
            assert processo is not None
            assert processo.status == 'AGUARDANDO_CIENCIA'
            processo_id = processo.id

        # =================================================================================
        # 2. FLUXO DO ALUNO (CIÊNCIA E DEFESA)
        # =================================================================================
        # Logout e Login do Aluno
        test_client.get('/logout')
        test_client.post('/login', data={'email': aluno_email, 'password': 'password123'}, follow_redirects=True)
        # Seleciona escola para o aluno também
        test_client.post('/select_school', data={'school_id': school_id}, follow_redirects=True)

        # Dar Ciente
        resp_ciente = test_client.post(f'/justica-e-disciplina/dar-ciente/{processo_id}', follow_redirects=True)
        assert resp_ciente.status_code == 200

        # Enviar Defesa
        payload_defesa = {'defesa': f'Minha defesa para o caso {tipo_escola}.'}
        resp_defesa = test_client.post(f'/justica-e-disciplina/enviar-defesa/{processo_id}', data=payload_defesa, follow_redirects=True)
        assert resp_defesa.status_code == 200
        assert b"sucesso" in resp_defesa.data or b"Defesa enviada" in resp_defesa.data

        # =================================================================================
        # 3. JULGAMENTO (ADMIN)
        # =================================================================================
        # Logout e Login do Admin novamente
        test_client.get('/logout')
        test_client.post('/login', data={'email': admin_email, 'password': 'password123'}, follow_redirects=True)
        test_client.post('/select_school', data={'school_id': school_id}, follow_redirects=True)

        # Analisar e Punir
        payload_decisao = {
            'decisao': 'punir',
            'pontos_finais': 1.5,
            'observacao_decisao': 'Defesa indeferida. Punição mantida.'
        }
        resp_final = test_client.post(f'/justica-e-disciplina/finalizar-processo/{processo_id}', data=payload_decisao, follow_redirects=True)
        assert resp_final.status_code == 200
        
        # Validar se a função de e-mail foi chamada
        assert mock_email.called, "O sistema deveria ter tentado enviar e-mail"

        # =================================================================================
        # 4. EXPORTAÇÃO PARA BI
        # =================================================================================
        resp_export = test_client.get('/justica-e-disciplina/exportar-selecao')
        assert resp_export.status_code == 200
        
        content_str = resp_export.data.decode('utf-8')
        # Verifica se os dados cruciais (Nome e Pontos) estão na exportação
        assert f"Sd Aluno {tipo_escola.upper()}" in content_str
        assert "1.5" in content_str

    print(f">>> TESTE DE {tipo_escola.upper()} FINALIZADO COM SUCESSO <<<")