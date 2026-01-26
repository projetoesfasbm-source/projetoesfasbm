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

# Fixture parametrizada que roda o setup 3 vezes (uma para cada tipo de escola)
@pytest.fixture(params=["cbfpm", "cspm", "ctsp"])
def setup_cenario_escola_tipo(request, test_app):
    tipo_escola = request.param
    with test_app.app_context():
        # 1. Criar Escola e Turma Configurada com o Tipo Atual
        # CORREÇÃO: Usando 'nome' em vez de 'name' conforme o modelo School
        school = School(nome=f"Escola Teste {tipo_escola.upper()}", npccal_type=tipo_escola)
        db.session.add(school)
        db.session.commit()

        turma = Turma(nome=f"Turma {tipo_escola.upper()}", school_id=school.id, ano=str(datetime.now().year))
        db.session.add(turma)
        db.session.commit()

        # 2. Criar Usuários (Admin e Aluno)
        # CORREÇÃO: Removemos 'password' do construtor e usamos set_password()
        # Admin
        admin_user = User(
            email=f"admin_{tipo_escola}@policia.rs.gov.br",
            nome_completo=f"Sgt Admin {tipo_escola.upper()}",
            role="admin_escola", # Role correta para gerenciar escola
            matricula=f"1000{tipo_escola}" # Matricula única
        )
        admin_user.set_password("password123")
        admin_user.is_active = True
        db.session.add(admin_user)
        
        # Aluno
        aluno_user = User(
            email=f"aluno_{tipo_escola}@policia.rs.gov.br",
            nome_completo=f"Sd Aluno {tipo_escola.upper()}",
            role="aluno",
            matricula=f"2000{tipo_escola}" # Matricula única
        )
        aluno_user.set_password("password123")
        aluno_user.is_active = True
        db.session.add(aluno_user)
        db.session.commit()

        # Perfil do Aluno vinculado à Turma
        aluno_profile = Aluno(user_id=aluno_user.id, turma_id=turma.id, numero=50, nome_guerra="Sd Teste")
        db.session.add(aluno_profile)
        
        # 3. Criar Regra Disciplinar Específica para o Tipo
        regra = DisciplineRule(
            npccal_type=tipo_escola,
            codigo="101",
            descricao=f"Infração Genérica {tipo_escola.upper()}",
            pontos=1.5
        )
        db.session.add(regra)
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
    Valida criação, defesa, julgamento e exportação.
    """
    dados = setup_cenario_escola_tipo
    tipo_escola = dados['tipo']
    school_id = dados['school'].id
    
    admin_email = dados['admin'].email
    aluno_email = dados['aluno_user'].email
    aluno_id = dados['aluno_profile'].id
    regra_id = dados['regra'].id

    print(f"\n>>> INICIANDO VALIDAÇÃO DE FLUXO PARA: {tipo_escola.upper()} <<<")

    # Mock do envio de email para não depender de SMTP externo
    with patch('backend.services.email_service.EmailService.send_email') as mock_email:
        mock_email.return_value = True

        # =================================================================================
        # 1. CRIAÇÃO DA INFRAÇÃO (ADMIN)
        # =================================================================================
        # Login como Admin
        test_client.post('/auth/login', data={'email': admin_email, 'password': 'password123'})
        
        # Simular seleção da escola na sessão (CRÍTICO para permissões multi-escola)
        with test_client.session_transaction() as sess:
            sess['active_school_id'] = school_id

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
        
        # Debug caso falhe
        if resp_create.status_code != 200:
            print(f"Erro ao criar registro: {resp_create.data.decode('utf-8')}")
            
        assert resp_create.status_code == 200
        assert b"sucesso" in resp_create.data

        # Verificar persistência no banco
        with test_app.app_context():
            processo = db.session.query(ProcessoDisciplina).filter_by(aluno_id=aluno_id).first()
            assert processo is not None
            assert processo.status == 'AGUARDANDO_CIENCIA'
            processo_id = processo.id

        # =================================================================================
        # 2. FLUXO DO ALUNO (CIÊNCIA E DEFESA)
        # =================================================================================
        test_client.get('/auth/logout')
        test_client.post('/auth/login', data={'email': aluno_email, 'password': 'password123'})
        
        # Setar escola ativa para o aluno também
        with test_client.session_transaction() as sess:
            sess['active_school_id'] = school_id

        # Dar Ciente
        resp_ciente = test_client.post(f'/justica-e-disciplina/dar-ciente/{processo_id}', follow_redirects=True)
        assert resp_ciente.status_code == 200

        # Enviar Defesa
        payload_defesa = {'defesa': f'Minha defesa para o caso {tipo_escola}.'}
        resp_defesa = test_client.post(f'/justica-e-disciplina/enviar-defesa/{processo_id}', data=payload_defesa, follow_redirects=True)
        assert resp_defesa.status_code == 200
        assert b"sucesso" in resp_defesa.data

        # =================================================================================
        # 3. JULGAMENTO (ADMIN)
        # =================================================================================
        test_client.get('/auth/logout')
        test_client.post('/auth/login', data={'email': admin_email, 'password': 'password123'})
        
        with test_client.session_transaction() as sess:
            sess['active_school_id'] = school_id

        # Analisar e Punir
        payload_decisao = {
            'decisao': 'punir',
            'pontos_finais': 1.5, # Pontos da regra
            'observacao_decisao': 'Defesa indeferida. Punição mantida.'
        }
        resp_final = test_client.post(f'/justica-e-disciplina/finalizar-processo/{processo_id}', data=payload_decisao, follow_redirects=True)
        assert resp_final.status_code == 200
        
        # Validar se Emails foram disparados
        assert mock_email.call_count >= 1

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