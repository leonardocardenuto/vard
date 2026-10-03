from __future__ import annotations

import argparse
import base64
import logging
import os
import signal
import sys
import threading
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from sqlalchemy import func, select

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.core.config import get_settings
from api.core.security import hash_password
from api.db import SessionLocal
from api.models import AppUser, Camera, UserCredential, Workspace, WorkspaceMember
from api.cache.model_hooks import register_cache_invalidation_hooks
from api.services.fall_monitor import CameraMonitorSupervisor


DEMO_AAD = b"vard/fall-event/v2"
DEFAULT_DEMO_EMAIL = "demo.webcam@example.com"
DEFAULT_DEMO_PASSWORD = "VardDemo2026!"
DEFAULT_DEMO_WORKSPACE_SLUG = "demo-webcam"


def parse_args():
    parser = argparse.ArgumentParser(description="Inicia os jobs de monitoramento de queda do VARD.")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Cria os dados locais de demonstração e adiciona a webcam deste computador ao monitoramento.",
    )
    parser.add_argument(
        "--demo-seed-only",
        action="store_true",
        help="Com --demo, cria os dados sem iniciar jobs ou abrir a webcam.",
    )
    parser.add_argument("--demo-email", default=DEFAULT_DEMO_EMAIL, help="E-mail da conta de demonstração.")
    parser.add_argument("--demo-password", default=DEFAULT_DEMO_PASSWORD, help="Senha da conta de demonstração.")
    parser.add_argument("--demo-workspace", default="Demonstração Webcam", help="Nome do workspace de demonstração.")
    parser.add_argument("--webcam-source", default="0", help="Índice ou origem OpenCV da webcam usada somente no modo demo.")
    parser.add_argument(
        "--demo-checkpoint",
        default=None,
        help="Checkpoint opcional aplicado apenas à câmera de demonstração.",
    )
    parser.add_argument("--demo-threshold", type=float, default=None, help="Limiar opcional aplicado apenas à câmera demo.")
    return parser.parse_args()


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main():
    args = parse_args()
    configure_logging()
    register_cache_invalidation_hooks()
    logger = logging.getLogger("fall_monitor.jobs")

    if args.demo:
        demo = seed_webcam_demo(args)
        logger.info(
            "Demo pronta: email=%s senha=%s workspace=%s camera=%s webcam=%s",
            args.demo_email,
            args.demo_password,
            demo["workspace_name"],
            demo["camera_name"],
            args.webcam_source,
        )
        if args.demo_seed_only:
            logger.info("Dados demo criados. Nenhuma webcam foi aberta por --demo-seed-only.")
            return

    stop_event = threading.Event()
    supervisor = CameraMonitorSupervisor(get_settings())

    def _stop(*_):
        logger.info("Encerrando jobs de monitoramento de cameras.")
        stop_event.set()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    supervisor.start()
    logger.info("Jobs de monitoramento ativos. Pressione Ctrl+C para encerrar.")
    try:
        while not stop_event.wait(1.0):
            pass
    finally:
        supervisor.stop()


def seed_webcam_demo(args) -> dict[str, str]:
    """Cria apenas os registros locais necessários para testar a webcam pelo app.

    A origem de webcam nunca é criada no fluxo normal do CLI. O registro demo é
    idempotente para que o mesmo comando possa ser usado antes de cada teste.
    """

    email = args.demo_email.strip().lower()
    if not email:
        raise ValueError("--demo-email não pode ser vazio")
    if len(args.demo_password) < 8:
        raise ValueError("--demo-password precisa ter pelo menos 8 caracteres")

    with SessionLocal() as db:
        user = db.scalar(select(AppUser).where(func.lower(AppUser.email) == email))
        if user is None:
            user = AppUser(email=email, full_name="Conta demonstração webcam")
            db.add(user)
            db.flush()
            db.add(UserCredential(user_id=user.id, password_hash=hash_password(args.demo_password)))

        if not user.encryption_public_key:
            _provision_demo_history_key(user, args.demo_password)

        workspace = db.scalar(select(Workspace).where(Workspace.slug == DEFAULT_DEMO_WORKSPACE_SLUG))
        if workspace is None:
            workspace = Workspace(
                name=args.demo_workspace.strip() or "Demonstração Webcam",
                slug=DEFAULT_DEMO_WORKSPACE_SLUG,
                timezone="America/Sao_Paulo",
                created_by_user_id=user.id,
            )
            db.add(workspace)
            db.flush()

        membership = db.get(WorkspaceMember, {"workspace_id": workspace.id, "user_id": user.id})
        if membership is None:
            db.add(
                WorkspaceMember(
                    workspace_id=workspace.id,
                    user_id=user.id,
                    role="owner",
                    status="active",
                    invited_by_user_id=user.id,
                )
            )
        elif membership.status != "active" or membership.role != "owner":
            membership.status = "active"
            membership.role = "owner"

        camera = db.scalar(
            select(Camera).where(
                Camera.workspace_id == workspace.id,
                Camera.external_id == "demo-local-webcam",
            )
        )
        if camera is None:
            camera = Camera(
                workspace_id=workspace.id,
                name="Webcam de demonstração",
                external_id="demo-local-webcam",
                connection_type="other",
                stream_url=str(args.webcam_source),
                status="offline",
                is_active=True,
                created_by_user_id=user.id,
            )
            db.add(camera)

        camera.name = "Webcam de demonstração"
        camera.connection_type = "other"
        camera.stream_url = str(args.webcam_source)
        camera.is_active = True
        camera.metadata_json = _demo_camera_metadata(args)
        db.commit()

        return {
            "workspace_name": workspace.name,
            "camera_name": camera.name,
        }


def _demo_camera_metadata(args) -> dict:
    monitor = {"enabled": not args.demo_seed_only}
    if args.demo_checkpoint:
        monitor["checkpoint"] = str(Path(args.demo_checkpoint).resolve())
    if args.demo_threshold is not None:
        monitor["threshold"] = args.demo_threshold
    return {
        "protocol": "local-agent-webcam",
        "demo": True,
        "fall_monitor": monitor,
    }


def _provision_demo_history_key(user: AppUser, password: str) -> None:
    private_key = X25519PrivateKey.generate()
    private_key_bytes = private_key.private_bytes_raw()
    salt = os.urandom(16)
    recovery_key = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    ).derive(password.encode("utf-8"))
    nonce = os.urandom(12)
    encrypted_backup = ChaCha20Poly1305(recovery_key).encrypt(nonce, private_key_bytes, DEMO_AAD)

    user.encryption_public_key = _encode(private_key.public_key().public_bytes_raw())
    user.encrypted_private_key_backup = f"{_encode(nonce)}.{_encode(encrypted_backup)}"
    user.encryption_recovery_salt = _encode(salt)


def _encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


if __name__ == "__main__":
    main()
