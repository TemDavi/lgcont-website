import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app, render_template


class EmailDeliveryError(RuntimeError):
    """Erro controlado para o chamador tratar uma falha de envio."""


def send_template_email(destinatario, assunto, template_name, texto_simples=None, **contexto):
    """Renderiza e envia um e-mail HTML, sempre com alternativa em texto simples."""
    config = current_app.config
    remetente = config.get("MAIL_DEFAULT_SENDER")

    if not config.get("MAIL_SERVER") or not remetente:
        current_app.logger.error("Envio de e-mail indisponível: configuração SMTP incompleta.")
        raise EmailDeliveryError("O servidor de e-mail ainda não foi configurado.")

    contexto.setdefault("nome_empresa", config.get("COMPANY_NAME", "LG Contabilidade"))
    contexto.setdefault("email_suporte", config.get("MAIL_SUPPORT_EMAIL") or remetente)
    try:
        html_renderizado = render_template(template_name, **contexto)
    except Exception:
        current_app.logger.exception("Falha ao renderizar um template de e-mail.")
        raise EmailDeliveryError("Não foi possível preparar o e-mail.") from None

    mensagem = EmailMessage()
    mensagem["Subject"] = assunto
    mensagem["From"] = remetente
    mensagem["To"] = destinatario
    mensagem.set_content(texto_simples or "Este e-mail contém conteúdo em HTML. Acesse-o em um cliente compatível.")
    # EmailMessage usa uma alternativa MIME HTML, equivalente ao campo html de extensões de e-mail.
    mensagem.add_alternative(html_renderizado, subtype="html")

    try:
        if config.get("MAIL_USE_SSL"):
            with smtplib.SMTP_SSL(
                config["MAIL_SERVER"],
                config["MAIL_PORT"],
                timeout=config["MAIL_TIMEOUT"],
                context=ssl.create_default_context(),
            ) as servidor:
                _autenticar_e_enviar(servidor, mensagem, config)
        else:
            with smtplib.SMTP(
                config["MAIL_SERVER"],
                config["MAIL_PORT"],
                timeout=config["MAIL_TIMEOUT"],
            ) as servidor:
                if config.get("MAIL_USE_TLS"):
                    servidor.starttls(context=ssl.create_default_context())
                _autenticar_e_enviar(servidor, mensagem, config)
    except (OSError, smtplib.SMTPException):
        # O traceback vai para o log, mas credenciais e conteúdo não são incluídos na mensagem.
        current_app.logger.exception("Falha no envio de um e-mail pelo serviço SMTP.")
        raise EmailDeliveryError("Não foi possível enviar o e-mail.") from None

    return True


def enviar_email_ativacao(destinatario, nome, link_ativacao):
    """Envia o e-mail usado pelo fluxo atual de aprovação e ativação do cliente."""
    config = current_app.config
    horas_expiracao = config["ACTIVATION_TOKEN_HOURS"]
    nome_empresa = config.get("COMPANY_NAME", "LG Contabilidade")
    texto_simples = (
        f"Olá, {nome or 'cliente'}!\n\n"
        f"Agradecemos pelo seu cadastro na {nome_empresa}. "
        "Confirme seu e-mail e crie sua senha acessando o link abaixo:\n\n"
        f"{link_ativacao}\n\n"
        f"Este link expira em {horas_expiracao} horas.\n"
        "Se você não solicitou este cadastro, ignore este e-mail."
    )
    return send_template_email(
        destinatario=destinatario,
        assunto="Verifique seu e-mail | LG Contabilidade",
        template_name="emails/verify_email.html",
        texto_simples=texto_simples,
        nome=nome,
        link_verificacao=link_ativacao,
        horas_expiracao=horas_expiracao,
    )


def _autenticar_e_enviar(servidor, mensagem, config):
    usuario = config.get("MAIL_USERNAME")
    senha = config.get("MAIL_PASSWORD")
    if usuario and senha:
        servidor.login(usuario, senha)
    servidor.send_message(mensagem)
