# backend/services/email_service.py

from flask import current_app, render_template
from threading import Thread
import os
import logging
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

log = logging.getLogger(__name__)

def send_async_email_brevo(app, to_email, subject, html_content):
    """Função que envia o e-mail com a API do Brevo numa thread separada."""
    with app.app_context():
        # Configuração da API do Brevo
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = os.environ.get('BREVO_API_KEY')

        if not configuration.api_key.get('api-key'):
            log.error("ERRO CRÍTICO: BREVO_API_KEY não encontrado nas variáveis de ambiente.")
            return

        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
        
        # Extrai o nome e o e-mail do remetente
        sender_str = os.environ.get('MAIL_DEFAULT_SENDER', '"Sistema EsFAS" <noreply@esfasbm.pythonanywhere.com>')
        if '<' in sender_str and '>' in sender_str:
            sender_name = sender_str.split('<')[0].strip().replace('"', '')
            sender_email = sender_str.split('<')[1].replace('>', '').strip()
        else:
            sender_name = "Sistema EsFAS"
            sender_email = sender_str.strip()
        
        sender = {"name": sender_name, "email": sender_email}
        to = [{"email": to_email}]

        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=to, 
            sender=sender, 
            subject=subject, 
            html_content=html_content
        )

        try:
            api_response = api_instance.send_transac_email(send_smtp_email)
            log.info(f"E-mail enviado via Brevo para: {to_email}. Response: {api_response}")
        except ApiException as e:
            log.error(f"FALHA AO ENVIAR E-MAIL COM BREVO para {to_email}")
            log.error(f"Erro: {e}", exc_info=True)

class EmailService:
    @staticmethod
    def send_password_reset_email(user, token):
        if not user.email:
            log.warning(f"Tentativa de enviar e-mail de redefinição para usuário sem e-mail: {user.matricula}")
            return None
            
        log.info(f"Preparando e-mail (Brevo API) para o utilizador: {user.email}")
        app = current_app._get_current_object()
        
        html_content = render_template(
            'email/redefinir_senha.html',
            user=user,
            token=token
        )

        subject = 'Redefinição de Senha - Sistema EsFAS'
        
        thr = Thread(target=send_async_email_brevo, args=[app, user.email, subject, html_content])
        thr.start()
        return thr

    @staticmethod
    def send_justice_notification_email(user, processo, url):
        """Envia e-mail notificando o aluno da abertura de um processo."""
        if not user.email:
            log.warning(f"Usuário {user.matricula} sem e-mail cadastrado para notificação de justiça.")
            return None

        log.info(f"Enviando notificação de ABERTURA de processo para: {user.email}")
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
        """Envia e-mail notificando o aluno do veredito final do processo."""
        if not user.email:
             log.warning(f"Usuário {user.matricula} sem e-mail cadastrado para veredito de justiça.")
             return None

        log.info(f"Enviando notificação de VEREDITO de processo para: {user.email}")
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