import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(r"C:\Users\Roderigo\OneDrive\Documentos\vard\vard\app\.env")
load_dotenv(ENV_PATH)


def send_reset_code(to_email: str, code: str):
    host = os.environ.get("SMTP_HOST")
    if not host:
        print(f"Codigo de redefinicao para {to_email}: {code}")
        print(f"Arquivo .env existe em {ENV_PATH}: {ENV_PATH.exists()}")
        return

    sender = os.environ.get("SMTP_FROM") or os.environ["SMTP_USER"]

    message = EmailMessage()
    message["Subject"] = "Seu codigo para redefinir a senha"
    message["From"] = sender
    message["To"] = to_email
    message.set_content(f"Seu codigo e {code}. Ele expira em 10 minutos.")

    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587"))) as server:
        server.starttls()
        server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        server.send_message(message)