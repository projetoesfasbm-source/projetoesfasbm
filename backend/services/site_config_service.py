from sqlalchemy import select
from backend.models.database import db
from backend.models.site_config import SiteConfig
import re

class SiteConfigService:
    """
    Serviço para leitura/escrita de configurações do site.
    Agora suporta também chaves do tipo 'number' (ex.: valor da hora-aula).
    """

    _DEFAULT_CONFIGS = [
        # Configurações gerais
        ('site_background', '', 'image', 'Imagem de fundo do site', 'general'),
        ('site_logo', '', 'image', 'Logo principal do site', 'general'),
        ('primary_color', '#3b82f6', 'color', 'Cor primária do site', 'general'),
        ('secondary_color', '#1a232c', 'color', 'Cor secundária do site', 'general'),
        ('navbar_background_image', '', 'image', 'Imagem de fundo da barra de navegação', 'general'),
        
        # Ícones do dashboard
        ('dashboard_card_alunos_icon', '👥', 'text', 'Ícone do card Alunos', 'dashboard'),
        ('dashboard_card_instrutores_icon', '🎓', 'text', 'Ícone do card Instrutores', 'dashboard'),
        ('dashboard_card_disciplinas_icon', '📚', 'text', 'Ícone do card Disciplinas', 'dashboard'),
        ('dashboard_card_historico_icon', '📊', 'text', 'Ícone do card Histórico', 'dashboard'),
        ('dashboard_card_assets_icon', '🎨', 'text', 'Ícone do card Assets', 'dashboard'),
        
        # Imagens de fundo dos cards
        ('dashboard_card_alunos_bg', '', 'image', 'Imagem de fundo do card Alunos', 'dashboard'),
        ('dashboard_card_instrutores_bg', '', 'image', 'Imagem de fundo do card Instrutores', 'dashboard'),
        ('dashboard_card_disciplinas_bg', '', 'image', 'Imagem de fundo do card Disciplinas', 'dashboard'),
        ('dashboard_card_historico_bg', '', 'image', 'Imagem de fundo do card Histórico', 'dashboard'),
        ('dashboard_card_assets_bg', '', 'image', 'Imagem de fundo do card Assets', 'dashboard'),
        ('dashboard_card_customizer_bg', '', 'image', 'Imagem de fundo do card Customizar', 'dashboard'),
        ('dashboard_header_bg', '', 'image', 'Imagem de fundo do cabeçalho do dashboard', 'dashboard'),
        
        # Sidebar
        ('sidebar_logo', '', 'image', 'Logo da sidebar', 'sidebar'),

        # Ícones das Turmas
        ('turma_1_icon', '', 'image', 'Ícone da Turma 1', 'turmas'),
        ('turma_2_icon', '', 'image', 'Ícone da Turma 2', 'turmas'),
        ('turma_3_icon', '', 'image', 'Ícone da Turma 3', 'turmas'),
        ('turma_4_icon', '', 'image', 'Ícone da Turma 4', 'turmas'),
        ('turma_5_icon', '', 'image', 'Ícone da Turma 5', 'turmas'),
        ('turma_6_icon', '', 'image', 'Ícone da Turma 6', 'turmas'),
        ('turma_7_icon', '', 'image', 'Ícone da Turma 7', 'turmas'),
        ('turma_8_icon', '', 'image', 'Ícone da Turma 8', 'turmas'),

        # Configurações de Relatórios
        ('report_chefe_ensino_cargo', 'Chefe da Seção de Ensino', 'text', 'Cargo padrão do Chefe de Ensino em relatórios', 'reports'),
        ('report_comandante_cargo', 'Comandante da EsFAS-SM', 'text', 'Cargo padrão do Comandante em relatórios', 'reports'),
        ('report_cidade_estado', 'Santa Maria - RS', 'text', 'Cidade e Estado padrão para relatórios', 'reports'),

        # ➕ NOVO: valor da hora-aula (número)
        ('report_valor_hora_aula', '55.19', 'number', 'Valor da hora-aula padrão usado em relatórios', 'reports'),
    ]

    _CONFIG_KEYS = {d[0]: {'type': d[2], 'category': d[4]} for d in _DEFAULT_CONFIGS}

    # ----------------------------
    # Helpers internos
    # ----------------------------
    @staticmethod
    def _parse_number_ptbr(value: str):
        """
        Converte strings como '1.234,56' ou '1234,56' ou '1234.56' para float.
        Retorna None se value for vazio/None.
        Levanta ValueError se não conseguir converter.
        """
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None
        s = str(value).strip()

        # Aceita formatos: 1234.56, 1.234,56, 1234,56, 1234
        # Estratégia: se tiver vírgula e ponto, assume '.' como milhar e ',' como decimal.
        if ',' in s and '.' in s:
            s = s.replace('.', '').replace(',', '.')
        elif ',' in s:
            s = s.replace(',', '.')
        # else: já está com ponto como decimal ou inteiro

        try:
            return float(s)
        except Exception:
            raise ValueError(f"Não foi possível interpretar '{value}' como número.")

    # ----------------------------
    # API pública
    # ----------------------------
    @staticmethod
    def get_config(key: str, default_value: str = None):
        """Obtém o valor de uma configuração (string)."""
        config = db.session.execute(
            select(SiteConfig).where(SiteConfig.config_key == key)
        ).scalar_one_or_none()
        return config.config_value if config else default_value

    @staticmethod
    def set_config(key: str, value: str, config_type: str = 'text', 
                   description: str = None, category: str = 'general', 
                   updated_by: int = None):
        """
        Define/atualiza uma configuração, validando o tipo com base no catálogo de chaves.
        """
        # 1) Validar chave (whitelist)
        if key not in SiteConfigService._CONFIG_KEYS:
            raise ValueError(f"Chave de configuração inválida: {key}")
        
        expected_type = SiteConfigService._CONFIG_KEYS[key]['type']
        if config_type != expected_type:
            raise ValueError(f"Tipo inválido para a chave {key}. Esperado: {expected_type}, Recebido: {config_type}")

        # 2) Validar o valor com base no tipo esperado
        if expected_type == 'image':
            # Permite vazio, caminho relativo em /static/uploads ou URL http/https (caso armazene CDN)
            if value and not (value.startswith('/static/uploads/') or value.startswith('http://') or value.startswith('https://')):
                raise ValueError(f"Valor inválido para configuração de imagem: {value}.")
        elif expected_type == 'color':
            if value and not re.match(r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$', value):
                raise ValueError(f"Valor inválido para cor: {value}. Esperado formato hexadecimal (#RRGGBB).")
        elif expected_type == 'number':
            # Apenas valida (consegue converter), mas armazena como string normalizada com ponto decimal.
            num = SiteConfigService._parse_number_ptbr(value)
            value = f"{num:.2f}" if num is not None else ""
        elif expected_type == 'text':
            # Texto simples (Jinja faz autoescape)
            pass

        # 3) Persistir
        config = db.session.execute(
            select(SiteConfig).where(SiteConfig.config_key == key)
        ).scalar_one_or_none()
        
        if config:
            config.config_value = value
            config.config_type = config_type
            config.description = description  # pode atualizar
            config.category = category        # pode atualizar
            config.updated_by = updated_by
        else:
            config = SiteConfig(
                config_key=key,
                config_value=value,
                config_type=config_type,
                description=description,
                category=category,
                updated_by=updated_by
            )
            db.session.add(config)
        
        return config

    @staticmethod
    def get_all_configs():
        """Retorna todas as configurações (objetos SiteConfig)."""
        return db.session.execute(select(SiteConfig)).scalars().all()
    
    @staticmethod
    def get_configs_by_category(category: str):
        """Retorna as configurações de uma categoria específica."""
        return db.session.execute(
            select(SiteConfig).where(SiteConfig.category == category)
        ).scalars().all()
    
    @staticmethod
    def init_default_configs():
        """
        Inicializa as configurações padrão (seed). Não faz commit aqui.
        """
        for key, value, config_type, description, category in SiteConfigService._DEFAULT_CONFIGS:
            existing = db.session.execute(
                select(SiteConfig).where(SiteConfig.config_key == key)
            ).scalar_one_or_none()
            if not existing:
                config = SiteConfig(
                    config_key=key,
                    config_value=value,
                    config_type=config_type,
                    description=description,
                    category=category
                )
                db.session.add(config)

    @staticmethod
    def delete_all_configs():
        """Remove todas as configs (cuidado). Não faz commit aqui."""
        db.session.query(SiteConfig).delete()

    # ----------------------------
    # Conveniências específicas
    # ----------------------------
    @staticmethod
    def get_valor_hora_aula(default: float = 55.19) -> float:
        """
        Retorna o valor da hora-aula (float). Lê 'report_valor_hora_aula' (tipo number).
        Aceita valores armazenados com vírgula (pt-BR) ou ponto.
        """
        raw = SiteConfigService.get_config('report_valor_hora_aula', None)
        if raw is None or str(raw).strip() == "":
            return float(default)
        try:
            return float(SiteConfigService._parse_number_ptbr(raw))
        except Exception:
            return float(default)

    @staticmethod
    def set_valor_hora_aula(value: float | str, updated_by: int = None):
        """
        Define o valor da hora-aula. Aceita float ou string ('55,19' ou '55.19').
        Persiste como string normalizada com ponto.
        """
        num = SiteConfigService._parse_number_ptbr(str(value))
        if num is None:
            raise ValueError("Valor da hora-aula não pode ser vazio.")
        return SiteConfigService.set_config(
            key='report_valor_hora_aula',
            value=f"{num:.2f}",
            config_type='number',
            description='Valor da hora-aula padrão usado em relatórios',
            category='reports',
            updated_by=updated_by
        )
