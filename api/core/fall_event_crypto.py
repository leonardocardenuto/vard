from __future__ import annotations

import base64
import hashlib
import hmac
import uuid
from datetime import UTC, datetime

from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class FallEventEncryptionError(ValueError):
    """Raised when the encryption key is missing or an event cannot be read."""


def encrypt_occurred_at(
    occurred_at: datetime,
    workspace_id: uuid.UUID,
    encryption_keys: str,
) -> str:
    value = _normalize_datetime(occurred_at).isoformat().encode("utf-8")
    return _workspace_cipher(workspace_id, encryption_keys).encrypt(value).decode("ascii")


def decrypt_occurred_at(
    encrypted_value: str,
    workspace_id: uuid.UUID,
    encryption_keys: str,
) -> datetime:
    try:
        value = _workspace_cipher(workspace_id, encryption_keys).decrypt(encrypted_value.encode("ascii"))
        return datetime.fromisoformat(value.decode("utf-8"))
    except (InvalidToken, UnicodeDecodeError, ValueError) as exc:
        raise FallEventEncryptionError("Não foi possível descriptografar o histórico de quedas.") from exc


def validate_encryption_keys(encryption_keys: str) -> None:
    _master_keys(encryption_keys)


def _workspace_cipher(workspace_id: uuid.UUID, encryption_keys: str) -> MultiFernet:
    context = b"vard/fall-event/v1/" + str(workspace_id).encode("ascii")
    derived_keys = []
    for master_key in _master_keys(encryption_keys):
        derived_key = hmac.new(master_key, context, hashlib.sha256).digest()
        derived_keys.append(Fernet(base64.urlsafe_b64encode(derived_key)))
    return MultiFernet(derived_keys)


def _master_keys(encryption_keys: str) -> list[bytes]:
    values = [value.strip() for value in encryption_keys.split(",") if value.strip()]
    if not values:
        raise FallEventEncryptionError("FALL_EVENT_ENCRYPTION_KEYS precisa estar configurada.")
    try:
        keys = [base64.urlsafe_b64decode(value.encode("ascii")) for value in values]
    except (UnicodeEncodeError, ValueError) as exc:
        raise FallEventEncryptionError("FALL_EVENT_ENCRYPTION_KEYS contém uma chave inválida.") from exc
    if any(len(key) != 32 for key in keys):
        raise FallEventEncryptionError("FALL_EVENT_ENCRYPTION_KEYS contém uma chave inválida.")
    return keys


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
