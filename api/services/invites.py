from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from api.core.config import get_settings

settings = get_settings()


class InviteEmailError(Exception):
    pass


def send_workspace_invite_email(to_email: str, workspace_name: str, invite_url: str, role: str) -> None:
    if not settings.sendgrid_api_key or not settings.sendgrid_from_email:
        raise InviteEmailError("SendGrid is not configured. Set SENDGRID_API_KEY and SENDGRID_FROM_EMAIL.")

    message = Mail(
        from_email=settings.sendgrid_from_email,
        to_emails=to_email,
        subject=f"Convite para workspace {workspace_name}",
        html_content=(
            f"<p>Você recebeu um convite para entrar no workspace <strong>{workspace_name}</strong>.</p>"
            f"<p>Perfil: <strong>{role}</strong></p>"
            f"<p><a href=\"{invite_url}\">Aceitar convite</a></p>"
        ),
    )

    try:
        client = SendGridAPIClient(settings.sendgrid_api_key)
        response = client.send(message)
    except Exception as exc:  # noqa: BLE001
        raise InviteEmailError(f"Failed to send invite email: {exc}") from exc

    if response.status_code >= 300:
        raise InviteEmailError(f"SendGrid returned status code {response.status_code}")
