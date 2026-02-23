# diagnostico_vinculos.py
import os
import sys
import json
from datetime import datetime, date
from sqlalchemy import inspect

# Adiciona o diretório atual ao path para garantir que os imports do backend funcionem
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.app import create_app
from backend.models.user import User

# Tenta importar relacionamentos de vínculo e perfis para análise aprofundada
try:
    from backend.models.user_school import UserSchool
    HAS_USER_SCHOOL = True
except ImportError:
    HAS_USER_SCHOOL = False

try:
    from backend.models.user_role import UserRole
    HAS_USER_ROLE = True
except ImportError:
    HAS_USER_ROLE = False


TARGET_IDS = ['2992779', '2612909', '3710653', '2886170']


def json_serial(obj):
    """Serializador JSON para tipos não suportados por padrão (ex: datetime)"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return str(obj)


def row2dict(row):
    """Converte um objeto SQLAlchemy num dicionário de forma dinâmica"""
    if not row:
        return {}
    d = {}
    for column in row.__table__.columns:
        d[column.name] = getattr(row, column.name)
    return d


def get_user_relationships(user):
    """Extrai dinamicamente dados de relacionamentos importantes do utilizador"""
    rels = {}
    
    # Verifica Perfis (Roles)
    if hasattr(user, 'roles'):
        try:
            rels['roles'] = [role.name if hasattr(role, 'name') else str(role) for role in user.roles]
        except Exception as e:
            rels['roles'] = f"Erro ao ler roles: {str(e)}"
    
    # Verifica Vínculos Escolares (UserSchools)
    if HAS_USER_SCHOOL and hasattr(user, 'user_schools'):
        try:
            escolas = []
            for us in user.user_schools:
                # Extrai dados do vínculo (ex: se está ativo, qual a escola, data)
                escola_data = {
                    'school_id': getattr(us, 'school_id', None),
                    'is_active': getattr(us, 'is_active', None),
                    'deleted_at': getattr(us, 'deleted_at', None)
                }
                escolas.append(escola_data)
            rels['vinculos_escolas'] = escolas
        except Exception as e:
            rels['vinculos_escolas'] = f"Erro ao ler user_schools: {str(e)}"
            
    return rels


def run_diagnostics():
    app = create_app()
    
    with app.app_context():
        print("="*60)
        print("🔍 A INICIAR DIAGNÓSTICO DE VÍNCULOS DE UTILIZADORES")
        print("="*60)
        
        # 1. Identifica dinamicamente qual coluna é usada para o "ID Funcional"
        mapper = inspect(User)
        col_names = [c.key for c in mapper.columns]
        
        id_col_name = None
        for candidate in ['id_funcional', 'matricula', 'username', 'login']:
            if candidate in col_names:
                id_col_name = candidate
                break
                
        if not id_col_name:
            print("❌ Falha: Não foi possível identificar a coluna de ID funcional na tabela User.")
            print(f"Colunas disponíveis: {col_names}")
            return
            
        print(f"✅ Coluna de identificação encontrada: '{id_col_name}'\n")

        # 2. Busca os utilizadores com problemas
        print(f"🔎 A procurar utilizadores alvos: {TARGET_IDS}")
        id_col_attr = getattr(User, id_col_name)
        target_users = User.query.filter(id_col_attr.in_(TARGET_IDS)).all()
        
        encontrados = [getattr(u, id_col_name) for u in target_users]
        nao_encontrados = list(set(TARGET_IDS) - set(encontrados))
        
        if nao_encontrados:
            print(f"⚠️ ATENÇÃO: Os seguintes IDs não existem na base de dados: {nao_encontrados}")
            
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "target_users": {},
            "healthy_users_baseline": {},
            "analysis_conclusion": []
        }

        # Extrai dados dos alvos
        for u in target_users:
            u_id = getattr(u, id_col_name)
            data = row2dict(u)
            data['relationships'] = get_user_relationships(u)
            report_data["target_users"][u_id] = data

        # 3. Busca uma baseline (utilizadores saudáveis) para comparação
        # Procura utilizadores que estejam ativos, não deletados e que possuam vínculos recentes
        print("🔎 A recolher amostra de utilizadores saudáveis para comparação...")
        
        query_healthy = User.query
        
        if 'is_active' in col_names:
            query_healthy = query_healthy.filter(User.is_active == True)
        if 'is_deleted' in col_names:
            query_healthy = query_healthy.filter(User.is_deleted == False)
        if 'deleted_at' in col_names:
            query_healthy = query_healthy.filter(User.deleted_at.is_(None))
            
        # Pega 5 utilizadores que não sejam os nossos alvos
        healthy_users = query_healthy.filter(~id_col_attr.in_(TARGET_IDS)).limit(5).all()
        
        for u in healthy_users:
            u_id = getattr(u, id_col_name)
            data = row2dict(u)
            data['relationships'] = get_user_relationships(u)
            report_data["healthy_users_baseline"][u_id] = data

        # 4. Análise e Comparação
        print("\n" + "="*60)
        print("📊 RELATÓRIO DE DISCREPÂNCIAS ENCONTRADAS")
        print("="*60)

        critical_fields = ['is_active', 'is_deleted', 'deleted_at', 'status', 'status_id']
        critical_fields = [f for f in critical_fields if f in col_names]
        
        for tgt_id, tgt_data in report_data["target_users"].items():
            print(f"\n👤 Utilizador Analisado: {tgt_data.get('nome', 'Sem Nome')} (ID: {tgt_id})")
            has_issue = False
            
            # Checa campos de status/exclusão lógica
            for field in critical_fields:
                val = tgt_data.get(field)
                # Valores problemáticos gerais
                if field == 'is_active' and val is False:
                    print(f"  ❌ is_active está FALSE. O utilizador está inativo.")
                    has_issue = True
                elif field == 'is_deleted' and val is True:
                    print(f"  ❌ is_deleted está TRUE. O utilizador foi removido logicamente.")
                    has_issue = True
                elif field == 'deleted_at' and val is not None:
                    print(f"  ❌ deleted_at preenchido ({val}). O utilizador foi removido logicamente.")
                    has_issue = True
                    
            # Checa Roles
            roles = tgt_data.get('relationships', {}).get('roles', [])
            if not roles:
                print(f"  ⚠️ O utilizador não possui perfis (Roles) atribuídos. A query de vínculo pode exigir um perfil (ex: Instrutor/Aluno).")
                has_issue = True
                
            # Verifica vínculos existentes
            vinculos = tgt_data.get('relationships', {}).get('vinculos_escolas', [])
            if vinculos:
                ativos = [v for v in vinculos if v.get('is_active', True) and not v.get('deleted_at')]
                if ativos:
                    print(f"  ℹ️ O utilizador JÁ POSSUI vínculos ativos com as escolas: {[v.get('school_id') for v in ativos]}.")
                    print(f"  (Isso pode ser o motivo de não aparecer na lista: o sistema oculta utilizadores já vinculados à escola atual).")

            if not has_issue:
                print("  ✅ Nenhum problema óbvio de status, deleção ou falta de perfil encontrado.")
                print("  👉 Possível causa externa: Cache da base de dados, permissões da escola do operador, ou bug no controller 'vinculo_controller.py'.")

        # 5. Salva o dump completo
        output_file = 'relatorio_diagnostico_vinculos.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, default=json_serial, indent=4, ensure_ascii=False)
            
        print("\n" + "="*60)
        print(f"✅ Diagnóstico finalizado com sucesso!")
        print(f"📄 Arquivo de análise detalhada salvo em: {os.path.abspath(output_file)}")
        print("="*60)


if __name__ == '__main__':
    run_diagnostics()