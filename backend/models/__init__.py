# backend/models/__init__.py

from .database import db

from .user import User
from .school import School
from .user_school import UserSchool
from .aluno import Aluno
from .instrutor import Instrutor
from .turma import Turma
from .ciclo import Ciclo
from .disciplina import Disciplina
from .disciplina_turma import DisciplinaTurma
from .horario import Horario
from .semana import Semana
from .historico import HistoricoAluno
from .historico_disciplina import HistoricoDisciplina
from .password_reset_token import PasswordResetToken
from .site_config import SiteConfig
from .image_asset import ImageAsset
from .turma_cargo import TurmaCargo
from .questionario import Questionario
from .pergunta import Pergunta
from .opcao_resposta import OpcaoResposta
from .resposta import Resposta
from .processo_disciplina import ProcessoDisciplina
from .notification import Notification
from .push_subscription import PushSubscription
from .fada_avaliacao import FadaAvaliacao


__all__ = [
    'db',
    'User',
    'School',
    'UserSchool',
    'Aluno',
    'Instrutor',
    'Turma',
    'Ciclo',
    'Disciplina',
    'DisciplinaTurma',
    'Horario',
    'Semana',
    'HistoricoAluno',
    'HistoricoDisciplina',
    'PasswordResetToken',
    'SiteConfig',
    'ImageAsset',
    'TurmaCargo',
    'Questionario',
    'Pergunta',
    'OpcaoResposta',
    'Resposta',
    'ProcessoDisciplina',
    'Notification',
    'PushSubscription' # <-- ADICIONE ESTA LINHA
]