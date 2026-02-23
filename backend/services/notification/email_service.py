"""
Serviço de envio de emails via SMTP.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config.base import (
    EMAIL_ENABLED,
    SMTP_FROM_EMAIL,
    SMTP_FROM_NAME,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USE_TLS,
    SMTP_USER,
)
from logging_config import get_logger

logger = get_logger("services.notification.email")


class EmailService:
    """Envia emails via SMTP."""

    def send(self, to: str, subject: str, html_body: str) -> bool:
        """Envia email via SMTP. Retorna True se sucesso."""
        if not EMAIL_ENABLED:
            logger.info(f"Email desabilitado, não enviando para {to}")
            return False

        if not SMTP_HOST:
            logger.warning("SMTP_HOST não configurado, email não enviado")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
            msg["To"] = to

            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                if SMTP_USE_TLS:
                    server.starttls()
                if SMTP_USER and SMTP_PASSWORD:
                    server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_FROM_EMAIL, to, msg.as_string())

            logger.info(f"Email enviado para {to}: {subject}")
            return True
        except Exception:
            logger.error(f"Erro ao enviar email para {to}", exc_info=True)
            return False

    def render_lembrete(
        self,
        titulo: str,
        descricao: str | None,
        data_evento: str | None,
        licitacao_numero: str | None = None,
    ) -> str:
        """Renderiza corpo HTML do email de lembrete."""
        licitacao_info = ""
        if licitacao_numero:
            licitacao_info = f"<p><strong>Licitação:</strong> {licitacao_numero}</p>"

        evento_info = ""
        if data_evento:
            evento_info = f"<p><strong>Data do evento:</strong> {data_evento}</p>"

        descricao_info = ""
        if descricao:
            descricao_info = f"<p>{descricao}</p>"

        return f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: #f59e0b; color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0;">LicitaFácil</h1>
            </div>
            <div style="padding: 20px; background: #f9fafb;">
                <h2>Lembrete: {titulo}</h2>
                {descricao_info}
                {evento_info}
                {licitacao_info}
            </div>
            <div style="padding: 10px 20px; background: #e5e7eb; text-align: center; font-size: 12px; color: #6b7280;">
                Este email foi enviado automaticamente pelo LicitaFácil.
            </div>
        </div>
        """


email_service = EmailService()
