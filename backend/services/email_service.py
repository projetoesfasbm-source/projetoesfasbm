# backend/services/email_service.py

import logging
import os
from threading import Thread
from flask import current_app, render_template
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

log = logging.getLogger(__name__)

def send_async_email_brevo(app, to_email, subject, html_content):
    """
    Função auxiliar que executa o envio de e-mail usando a API da Brevo
    dentro de uma thread separada para não travar a aplicação principal.
    """
    with app.app_context():
        # 1. Configuração da API Key da Brevo
        configuration = sib_api_v3_sdk.Configuration()
        # A chave continua vindo do .env por segurança
        configuration.api_key['api-key'] = os.environ.get('BREVO_API_KEY')

        if not configuration.api_key.get('api-key'):
            log.error("ERRO CRÍTICO DE E-MAIL: BREVO_API_KEY não encontrada nas variáveis de ambiente (.env).")
            return

        # 2. Inicializa o cliente da API
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
        
        # 3. Configura o Remetente (Sender) - FIXO conforme solicitado
        # Isso garante que use exatamente o e-mail que funcionou no seu teste.
        sender = {"name": "Sistema EsFAS", "email": "projetoesfasbm@gmail.com"}
        
        # Configura o destinatário
        to = [{"email": to_email}]

        # 4. Prepara o objeto de envio
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=to, 
            sender=sender, 
            subject=subject, 
            html_content=html_content
        )

        # 5. Tenta enviar
        try:
            api_response = api_instance.send_transac_email(send_smtp_email)
            log.info(f"SUCESSO: E-mail enviado via Brevo para {to_email}. ID: {api_response.message_id}")
        except ApiException as e:
            log.error(f"FALHA AO ENVIAR E-MAIL BREVO para {to_email}.")
            log.error(f"Status Code: {e.status}")
            log.error(f"Detalhe do Erro: {e.body}")
        except Exception as e:
            log.exception(f"ERRO INESPERADO ao tentar enviar e-mail para {to_email}: {str(e)}")

class EmailService:
    """
    Serviço centralizado para envio de e-mails transacionais do sistema.
    """

    @staticmethod
    def send_password_reset_email(user, token):
        """Envia e-mail de redefinição de senha com o token gerado."""
        if not user.email:
            log.warning(f"Tentativa de envio de e-mail de senha para usuário sem e-mail: {user.matricula}")
            return None
            
        log.info(f"Iniciando processo de envio de e-mail de SENHA para: {user.email}")
        app = current_app._get_current_object()
        
        # Renderiza o template HTML com os dados necessários
        html_content = render_template(
            'email/redefinir_senha.html',
            user=user,
            token=token
        )

        subject = 'Redefinição de Senha - Sistema EsFAS'
        
        # Inicia a thread para envio assíncrono
        thr = Thread(target=send_async_email_brevo, args=[app, user.email, subject, html_content])
        thr.start()
        return thr

    @staticmethod
    def send_justice_notification_email(user, processo, url):
        """Envia e-mail notificando o aluno da ABERTURA de um processo disciplinar."""
        if not user.email:
            log.warning(f"Usuário {user.matricula} sem e-mail cadastrado para notificação de justiça.")
            return None

        log.info(f"Iniciando processo de envio de notificação de JUSTIÇA (Abertura) para: {user.email}")
        app = current_app._get_current_object()
        
        html_content = render_template(
            'email/notificacao_justica.html',
            user=user,
            processo=processo,
            url=url
        )

        subject = f'Notificação de Processo Disciplinar - Nº {processo.id}'
        
        thr = Thread(target=send_async_email_brevo, args=[app, user.email, subject, html_content])
        thr.start()
        return thr

    @staticmethod
    def send_justice_verdict_email(user, processo):
        """Envia e-mail notificando o aluno do VEREDITO FINAL de um processo."""
        if not user.email:
             log.warning(f"Usuário {user.matricula} sem e-mail cadastrado para veredito de justiça.")
             return None

        log.info(f"Iniciando processo de envio de notificação de JUSTIÇA (Veredito) para: {user.email}")
        app = current_app._get_current_object()
        
        html_content = render_template(
            'email/veredito_justica.html',
            user=user,
            processo=processo
        )

        subject = f'Decisão de Processo Disciplinar - Nº {processo.id}'
        
        thr = Thread(target=send_async_email_brevo, args=[app, user.email, subject, html_content])
        thr.start()
        return thr