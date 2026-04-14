## Plan: Corrigir fluxo de reset 2FA

TL;DR - Implementar o botão e o e-mail de reset 2FA no fluxo de verificação, adicionando envio via EmailService e suporte ao formulário de solicitação com CSRF.

**Steps**
1. Atualizar `backend/controllers/auth_controller.py`
   - Em `verificar_2fa`, instanciar um segundo formulário `reset_form = CSRFOnlyForm()` e passar para o template.
   - Criar um helper de serializador mais flexível, mantendo compatibilidade com reset de senha e adicionando salt específico para 2FA (`reset-2fa`).
   - Ajustar `solicitar_reset_2fa` e `resetar_2fa_token` se necessário para usar o serializador correto.

2. Adicionar suporte ao envio de e-mail de reset 2FA em `backend/services/email_service.py`
   - Implementar `EmailService.send_2fa_reset_email(user, token)`.
   - Reutilizar a arquitetura de envio assíncrono já existente, com template HTML e thread.

3. Criar template de e-mail `templates/email/reset_2fa.html`
   - Incluir link de recuperação usando `url_for('auth.resetar_2fa_token', token=token, _external=True)`.
   - Manter estilo similar ao e-mail de redefinição de senha existente.

4. Atualizar `templates/auth/verify_2fa.html`
   - Adicionar botão/link para solicitar reset 2FA no fluxo de verificação.
   - Incluir segundo formulário POST com CSRF para `auth.solicitar_reset_2fa`.

**Relevant files**
- `CODIGO_FONTE/backend/controllers/auth_controller.py`
- `CODIGO_FONTE/backend/services/email_service.py`
- `CODIGO_FONTE/templates/auth/verify_2fa.html`
- `CODIGO_FONTE/templates/email/reset_2fa.html`

**Verification**
1. A página `verify_2fa` deve exibir botão "Esqueci meu aparelho" ou similar.
2. Ao clicar em reset, o código deve gerar token e chamar `EmailService.send_2fa_reset_email`.
3. O token de reset deve ser validado em `resetar_2fa_token` e desabilitar `totp_secret` / `is_totp_enabled`.
4. Caso não haja email configurado, o console deve exibir o link de recuperação como fallback.

**Decisions**
- Implementar o método de e-mail diretamente, em vez de depender apenas do fallback de console.
- Usar template separado para e-mail de 2FA, garantindo clareza de comunicação.
- Não alterar a lógica de login 2FA existente além do necessário para suportar a solicitação de reset.

**Further Considerations**
1. Se você quiser, posso também adicionar uma página de confirmação dedicada após a solicitação de reset 2FA, em vez de redirecionar direto para `login`.
