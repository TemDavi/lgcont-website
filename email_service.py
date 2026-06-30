import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app


class EmailDeliveryError(RuntimeError):
    """Erro controlado para impedir a aprovação quando o e-mail não sair."""


def enviar_email_ativacao(destinatario, nome, link_ativacao):
    config = current_app.config
    remetente = config.get("MAIL_DEFAULT_SENDER")

    if not config.get("MAIL_SERVER") or not remetente:
        raise EmailDeliveryError("O servidor de e-mail ainda não foi configurado.")

    mensagem = EmailMessage()
    mensagem["Subject"] = "Seu acesso à área do cliente"
    mensagem["From"] = remetente
    mensagem["To"] = destinatario
    mensagem.set_content(
        f"Olá, {nome}!\n\n"
        "Seu cadastro foi aprovado. Use o link abaixo para criar sua senha:\n\n"
        f"{link_ativacao}\n\n"
        f"O link expira em {config['ACTIVATION_TOKEN_HOURS']} horas. "
        "Se você não solicitou este cadastro, ignore esta mensagem."
    )

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
    except (OSError, smtplib.SMTPException) as erro:
        raise EmailDeliveryError("Não foi possível enviar o e-mail de ativação.") from erro


def _autenticar_e_enviar(servidor, mensagem, config):
    usuario = config.get("MAIL_USERNAME")
    senha = config.get("MAIL_PASSWORD")
    if usuario and senha:
        servidor.login(usuario, senha)
    servidor.send_message(mensagem)
