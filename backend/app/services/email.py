import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlencode

from app.core.config import settings


class EmailDeliveryError(RuntimeError):
    pass


def email_delivery_configured() -> bool:
    return bool(settings.SMTP_HOST and (settings.EMAIL_FROM or settings.SMTP_USERNAME))


def send_password_reset_email(recipient: str, token: str) -> None:
    sender = settings.EMAIL_FROM or settings.SMTP_USERNAME
    if not email_delivery_configured():
        raise EmailDeliveryError("SMTP email delivery is not configured.")

    reset_url = (
        f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?"
        f"{urlencode({'token': token})}"
    )
    message = EmailMessage()
    message["Subject"] = "Reset your Catholic Readings account password"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "A password reset was requested for your account.\n\n"
        f"Use this link within one hour to choose a new password:\n{reset_url}\n\n"
        "If you did not request this change, you can ignore this email."
    )

    try:
        if settings.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=20,
                context=ssl.create_default_context(),
            ) as smtp:
                _deliver(smtp, sender, recipient, message)
        else:
            with smtplib.SMTP(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=20,
            ) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                _deliver(smtp, sender, recipient, message)
    except (OSError, smtplib.SMTPException) as error:
        raise EmailDeliveryError("Unable to deliver the password reset email.") from error


def _deliver(
    smtp: smtplib.SMTP | smtplib.SMTP_SSL,
    sender: str,
    recipient: str,
    message: EmailMessage,
) -> None:
    if settings.SMTP_USERNAME:
        smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
    smtp.send_message(message, from_addr=sender, to_addrs=[recipient])
