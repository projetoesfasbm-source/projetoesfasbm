# backend/services/site_config_service.py

from sqlalchemy import select
from backend.models.database import db
from backend.models.site_config import SiteConfig
import re

class SiteConfigService:
    """
    Serviço para leitura/escrita de configurações do site.
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
        ('report_valor_hora_aula', '55.19', 'number', 'Valor da hora-aula padrão usado em relatórios', 'reports'),

        # Horários dos Períodos
        ('horario_periodo_01', '07:30-08:15', 'text', '1º Período', 'horarios'),
        ('horario_periodo_02', '08:15-09:00', 'text', '2º Período', 'horarios'),
        ('horario_periodo_03', '09:00-09:45', 'text', '3º Período', 'horarios'),
        ('horario_intervalo_1', '09:45-10:00', 'text', 'Intervalo Manhã', 'horarios'),
        ('horario_periodo_04', '10:00-10:45', 'text', '4º Período', 'horarios'),
        ('horario_periodo_05', '10:45-11:30', 'text', '5º Período', 'horarios'),
        ('horario_periodo_06', '11:30-12:15', 'text', '6º Período', 'horarios'),
        ('horario_almoco', '12:15-13:45', 'text', 'Intervalo Almoço', 'horarios'),
        ('horario_periodo_07', '13:45-14:30', 'text', '7º Período', 'horarios'),
        ('horario_periodo_08', '14:30-15:15', 'text', '8º Período', 'horarios'),
        ('horario_periodo_09', '15:15-16:00', 'text', '9º Período', 'horarios'),
        ('horario_intervalo_2', '16:00-16:15', 'text', 'Intervalo Tarde', 'horarios'),
        ('horario_periodo_10', '16:15-17:00', 'text', '10º Período', 'horarios'),
        ('horario_periodo_11', '17:00-17:45', 'text', '11º Período', 'horarios'),
        ('horario_periodo_12', '17:45-18:30', 'text', '12º Período', 'horarios'),
        ('horario_periodo_13', '18:30-19:15', 'text', '13º Período (Extra)', 'horarios'),
        ('horario_periodo_14', '19:15-20:00', 'text', '14º Período (Extra)', 'horarios'),
        ('horario_periodo_15', '20:00-20:45', 'text', '15º Período (Extra)', 'horarios'),
    ]

    _CONFIG_KEYS = {d[0]: {'type': d[2], 'category': d[4]} for d in _DEFAULT_CONFIGS}
    _DEFAULTS_MAP = {d[0]: d[1] for d in _DEFAULT_CONFIGS}

    @staticmethod
    def get_config(key: str, default_value: str = None):
        config = db.session.execute(
            select(SiteConfig).where(SiteConfig.config_key == key)
        ).scalar_one_or_none()
        if config is not None:
            return config.config_value
        if key in SiteConfigService._DEFAULTS_MAP:
            return SiteConfigService._DEFAULTS_MAP[key]
        return default_value

    @staticmethod
    def get_all_configs():
        db_configs = db.session.execute(select(SiteConfig)).scalars().all()
        db_configs_map = {c.config_key: c for c in db_configs}
        final_configs = []
        for key, value, config_type, description, category in SiteConfigService._DEFAULT_CONFIGS:
            if key in db_configs_map:
                final_configs.append(db_configs_map[key])
            else:
                temp_config = SiteConfig(
                    config_key=key, config_value=value, config_type=config_type,
                    description=description, category=category
                )
                final_configs.append(temp_config)
        return final_configs

    @staticmethod
    def get_configs_by_category(category: str):
        all_configs = SiteConfigService.get_all_configs()
        return [c for c in all_configs if c.category == category]

    @staticmethod
    def init_default_configs():
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
    
    # --- O restante do ficheiro permanece igual ---

    @staticmethod
    def _parse_number_ptbr(value: str):
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None
        s = str(value).strip()
        if ',' in s and '.' in s:
            s = s.replace('.', '').replace(',', '.')
        elif ',' in s:
            s = s.replace(',', '.')
        try:
            return float(s)
        except Exception:
            raise ValueError(f"Não foi possível interpretar '{value}' como número.")

    @staticmethod
    def set_config(key: str, value: str, config_type: str = 'text', 
                   description: str = None, category: str = 'general', 
                   updated_by: int = None):
        if key not in SiteConfigService._CONFIG_KEYS:
            raise ValueError(f"Chave de configuração inválida: {key}")
        
        expected_type = SiteConfigService._CONFIG_KEYS[key]['type']
        if config_type != expected_type:
            raise ValueError(f"Tipo inválido para a chave {key}. Esperado: {expected_type}, Recebido: {config_type}")

        if expected_type == 'image':
            if value and not (value.startswith('/static/uploads/') or value.startswith('http://') or value.startswith('https://')):
                raise ValueError(f"Valor inválido para configuração de imagem: {value}.")
        elif expected_type == 'color':
            if value and not re.match(r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$', value):
                raise ValueError(f"Valor inválido para cor: {value}. Esperado formato hexadecimal (#RRGGBB).")
        elif expected_type == 'number':
            num = SiteConfigService._parse_number_ptbr(value)
            value = f"{num:.2f}" if num is not None else ""
        elif expected_type == 'text':
            pass

        config = db.session.execute(
            select(SiteConfig).where(SiteConfig.config_key == key)
        ).scalar_one_or_none()
        
        if config:
            config.config_value = value
            config.config_type = config_type
            config.description = description
            config.category = category
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
    def delete_all_configs():
        db.session.query(SiteConfig).delete()

    @staticmethod
    def get_valor_hora_aula(default: float = 55.19) -> float:
        raw = SiteConfigService.get_config('report_valor_hora_aula', None)
        if raw is None or str(raw).strip() == "":
            return float(default)
        try:
            return float(SiteConfigService._parse_number_ptbr(raw))
        except Exception:
            return float(default)

    @staticmethod
    def set_valor_hora_aula(value: float | str, updated_by: int = None):
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