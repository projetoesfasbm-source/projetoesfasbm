import pytest
from unittest.mock import patch
from datetime import datetime
from flask import session
from flask_login import login_user
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
    # Desabilita CSRF completamente. Isso evita validação E renderização se configurado certo.
    test_app.config['WTF_CSRF_ENABLED'] = False 
    test_app.config['WTF_CSRF_CHECK_DEFAULT'] = False

    tipo_escola = request.param
    with test_app.app_context():
        # 1. Criar Escola e Turma
        school = School(nome=f"Escola Teste {tipo_escola.upper()}", npccal_type=tipo_escola)
        db.session.add(school)
        db.session.flush()

        turma = Turma(nome=f"Turma {tipo_escola.upper()}", school_id=school.id, ano=str(datetime.now().year))
        db.session.add(turma)
        
        # 2. Criar Admin
        admin_user = User(
            email=f"admin_{tipo_escola}@policia.rs.gov.br",
            nome_completo=f"Sgt Admin {tipo_escola.upper()}",
            role="admin_escola", 
            matricula=f"1000{tipo_escola}" 
        )
        admin_user.set_password("password123")
        admin_user.is_active = True
        db.session.add(admin_user)
        db.session.flush() 
        
        # Vínculo Admin-Escola
        user_school = UserSchool(user_id=admin_user.id, school_id=school.id, role="admin_escola")
        db.session.add(user_school)
        
        # 3. Criar Aluno (Usuário)
        aluno_user = User(
            email=f"aluno_{tipo_escola}@policia.rs.gov.br",
            nome_completo=f"Sd Aluno {tipo_escola.upper()}",
            role="aluno",
            matricula=f"2000{tipo_escola}" 
        )
        aluno_user.set_password("password123")
        aluno_user.is_active = True
        db.session.add(aluno_user)
        db.session.flush() 
        
        # Vínculo Aluno-Escola
        user_school_aluno = UserSchool(user_id=aluno_user.id, school_id=school.id, role="aluno")
        db.session.add(user_school_aluno)

        # 4. Perfil Aluno
        aluno_profile = Aluno(
            user_id=aluno_user.id, 
            turma_id=turma.id, 
            opm="1º BPM" 
        )
        db.session.add(aluno_profile)
        
        # 5. Regra Disciplinar
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
    Testa o ciclo de vida completo de um processo disciplinar.
    """
    dados = setup_cenario_escola_tipo
    tipo_escola = dados['tipo']
    school_id = dados['school'].id
    
    admin_user = dados['admin']
    aluno_user = dados['aluno_user']
    aluno_id = dados['aluno_profile'].id
    regra_id = dados['regra'].id

    print(f"\n>>> INICIANDO VALIDAÇÃO DE FLUXO PARA: {tipo_escola.upper()} <<<")

    with patch('backend.services.email_service.send_async_email_brevo') as mock_email:
        
        # =================================================================================
        # 1. CRIAÇÃO DA INFRAÇÃO (ADMIN)
        # =================================================================================
        
        # ESTRATÉGIA DE LOGIN DEFINITIVA: Usar sessões de teste manuais com todos os campos necessários
        with test_client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
            # IMPORTANTE: Força o ID da escola na sessão para evitar redirect para /select_school
            sess['active_school_id'] = school_id 
            sess['active_school_role'] = 'admin_escola'
            sess['active_school_name'] = dados['school'].nome

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
        
        if b"Login" in resp_create.data:
             pytest.fail(f"Falha de autenticação (Admin). Redirect para Login detectado.")

        assert resp_create.status_code == 200
        # Aceita "sucesso" ou "registros criados" ou o título da página de index da justiça
        assert any(x in resp_create.data for x in [b"sucesso", b"registros criados", b"Justi", b"table"])

        # Verificar persistência no banco
        with test_app.app_context():
            processo = db.session.query(ProcessoDisciplina).filter_by(aluno_id=aluno_id).first()
            assert processo is not None
            assert processo.status == 'AGUARDANDO_CIENCIA'
            processo_id = processo.id

        # =================================================================================
        # 2. FLUXO DO ALUNO (CIÊNCIA E DEFESA)
        # =================================================================================
        with test_client.session_transaction() as sess:
            sess['_user_id'] = str(aluno_user.id)
            sess['active_school_id'] = school_id
            sess['active_school_role'] = 'aluno' # Define o papel correto
            sess['_fresh'] = True

        # Dar Ciente
        resp_ciente = test_client.post(f'/justica-e-disciplina/dar-ciente/{processo_id}', follow_redirects=True)
        assert resp_ciente.status_code == 200

        # Enviar Defesa
        payload_defesa = {'defesa': f'Minha defesa para o caso {tipo_escola}.'}
        resp_defesa = test_client.post(f'/justica-e-disciplina/enviar-defesa/{processo_id}', data=payload_defesa, follow_redirects=True)
        
        if b"Login" in resp_defesa.data:
             pytest.fail(f"Falha de autenticação (Aluno). Redirect para Login detectado.")
             
        assert resp_defesa.status_code == 200
        assert b"sucesso" in resp_defesa.data or b"Defesa enviada" in resp_defesa.data or b"Justi" in resp_defesa.data

        # =================================================================================
        # 3. JULGAMENTO (ADMIN)
        # =================================================================================
        with test_client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['active_school_id'] = school_id
            sess['active_school_role'] = 'admin_escola'
            sess['_fresh'] = True

        payload_decisao = {
            'decisao': 'punir',
            'pontos_finais': 1.5,
            'observacao_decisao': 'Defesa indeferida. Punição mantida.'
        }
        resp_final = test_client.post(f'/justica-e-disciplina/finalizar-processo/{processo_id}', data=payload_decisao, follow_redirects=True)
        assert resp_final.status_code == 200
        
        assert mock_email.called

        # =================================================================================
        # 4. EXPORTAÇÃO PARA BI
        # =================================================================================
        resp_export = test_client.get('/justica-e-disciplina/exportar-selecao')
        assert resp_export.status_code == 200
        
        content_str = resp_export.data.decode('utf-8')
        assert f"Sd Aluno {tipo_escola.upper()}" in content_str
        assert "1.5" in content_str

    print(f">>> TESTE DE {tipo_escola.upper()} FINALIZADO COM SUCESSO <<<")