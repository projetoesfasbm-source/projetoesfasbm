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

# Fixture parametrizada que roda o setup 3 vezes (uma para cada tipo)
# Mudança: 'app' substituído por 'test_app' para compatibilidade com o conftest.py
@pytest.fixture(params=["cbfpm", "cspm", "ctsp"])
def setup_cenario_escola_tipo(request, test_app):
    tipo_escola = request.param
    with test_app.app_context():
        # 1. Criar Escola e Turma Configurada com o Tipo Atual
        # O nome inclui o tipo para facilitar identificação em logs de erro
        school = School(name=f"Escola Teste {tipo_escola.upper()}", npccal_type=tipo_escola)
        db.session.add(school)
        db.session.commit()

        turma = Turma(nome=f"Turma {tipo_escola.upper()}", school_id=school.id)
        db.session.add(turma)
        db.session.commit()

        # 2. Criar Usuários (Admin e Aluno)
        # Usamos sufixos nos emails para garantir unicidade entre as iterações do teste
        admin_user = User(
            email=f"admin_{tipo_escola}@policia.rs.gov.br",
            password="password123",
            nome_completo=f"Sgt Admin {tipo_escola.upper()}",
            role="admin",
            can_manage_justice=True
        )
        db.session.add(admin_user)
        
        aluno_user = User(
            email=f"aluno_{tipo_escola}@policia.rs.gov.br",
            password="password123",
            nome_completo=f"Sd Aluno {tipo_escola.upper()}",
            role="aluno"
        )
        db.session.add(aluno_user)
        db.session.commit()

        aluno_profile = Aluno(user_id=aluno_user.id, turma_id=turma.id, numero=50)
        db.session.add(aluno_profile)
        
        # 3. Criar Regra Disciplinar Específica para o Tipo
        # O sistema pode filtrar regras pelo npccal_type, então criamos uma compatível
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

# Mudança: 'client' substituído por 'test_client'
def test_fluxo_completo_justica_todas_escolas(test_client, setup_cenario_escola_tipo):
    """
    Testa o ciclo de vida completo de um processo disciplinar para CBFPM, CSPM e CTSP.
    """
    dados = setup_cenario_escola_tipo
    tipo_escola = dados['tipo']
    
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
        # Usando test_client em vez de client
        test_client.post('/auth/login', data={'email': admin_email, 'password': 'password123'})
        
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
        assert resp_create.status_code == 200, f"Falha ao criar registro para {tipo_escola}"
        assert b"sucesso" in resp_create.data

        # Verificar persistência no banco
        # Usando test_client.application.app_context() para acessar o banco
        with test_client.application.app_context():
            processo = db.session.query(ProcessoDisciplina).filter_by(aluno_id=aluno_id).first()
            assert processo is not None
            assert processo.status == 'AGUARDANDO_CIENCIA'
            processo_id = processo.id

        # =================================================================================
        # 2. FLUXO DO ALUNO (CIÊNCIA E DEFESA)
        # =================================================================================
        test_client.get('/auth/logout')
        test_client.post('/auth/login', data={'email': aluno_email, 'password': 'password123'})

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

        # Analisar e Punir
        payload_decisao = {
            'decisao': 'punir',
            'pontos_finais': 1.5, # Pontos da regra
            'observacao_decisao': 'Defesa indeferida. Punição mantida.'
        }
        resp_final = test_client.post(f'/justica-e-disciplina/finalizar-processo/{processo_id}', data=payload_decisao, follow_redirects=True)
        assert resp_final.status_code == 200
        
        # Validar Emails enviados (Notificação inicial + Veredito)
        assert mock_email.call_count >= 1, "Pelo menos um email deveria ter sido disparado"

        # =================================================================================
        # 4. VALIDAÇÃO DE DADOS PÓS-JULGAMENTO
        # =================================================================================
        with test_client.application.app_context():
            p = db.session.get(ProcessoDisciplina, processo_id)
            assert p.status == 'FINALIZADO'
            assert p.decisao_final == 'punir'
            assert p.pontos == 1.5
            
            # Validação: A regra vinculada deve ser do tipo correto da escola
            regra_db = db.session.get(DisciplineRule, p.regra_id)
            assert regra_db.npccal_type == tipo_escola

        # =================================================================================
        # 5. EXPORTAÇÃO PARA BI
        # =================================================================================
        resp_export = test_client.get('/justica-e-disciplina/exportar-selecao')
        assert resp_export.status_code == 200
        
        content_str = resp_export.data.decode('utf-8')
        # Verifica se os dados cruciais estão na exportação independente do tipo de escola
        assert f"Sd Aluno {tipo_escola.upper()}" in content_str
        assert "1.5" in content_str
        assert "punir" in content_str.lower() or "PUNIR" in content_str

    print(f">>> TESTE DE {tipo_escola.upper()} FINALIZADO COM SUCESSO <<<")