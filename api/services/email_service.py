import os
import smtplib
from email.message import EmailMessage


def send_reset_code(to_email: str, code: str) -> None:
    host = os.environ.get("SMTP_HOST")
    if not host:
        print(f"Código de redefinição para {to_email}: {code}")
        return

    sender = os.environ.get("SMTP_FROM") or os.environ["SMTP_USER"]

    message = EmailMessage()
    message["Subject"] = "Seu código para redefinir a senha"
    message["From"] = sender
    message["To"] = to_email
    message.set_content(f"Seu código é {code}. Ele expira em 10 minutos.")

    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587"))) as server:
        server.starttls()
        server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        server.send_message(message)
