from __future__ import annotations

import base64
import os
import uuid
from datetime import UTC, datetime

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_AAD = b"vard/fall-event/v2"


def encrypt_for_recipients(occurred_at: datetime, recipient_public_keys: dict[uuid.UUID, str]) -> tuple[str, dict[str, dict[str, str]]]:
    ciphertext, envelopes = encrypt_bytes_for_recipients(
        occurred_at.astimezone(UTC).isoformat().encode("utf-8"), recipient_public_keys
    )
    return _encode(ciphertext), envelopes


def encrypt_bytes_for_recipients(value: bytes, recipient_public_keys: dict[uuid.UUID, str]) -> tuple[bytes, dict[str, dict[str, str]]]:
    if not recipient_public_keys:
        raise ValueError("Nenhum membro autorizado possui chave de criptografia.")
    content_key = os.urandom(32)
    nonce = os.urandom(12)
    encrypted_payload = nonce + ChaCha20Poly1305(content_key).encrypt(nonce, value, _AAD)
    envelopes: dict[str, dict[str, str]] = {}
    for user_id, encoded_public_key in recipient_public_keys.items():
        public_key = X25519PublicKey.from_public_bytes(_decode(encoded_public_key))
        ephemeral_private_key = X25519PrivateKey.generate()
        wrap_nonce = os.urandom(12)
        wrapping_key = _derive_key(ephemeral_private_key.exchange(public_key))
        ciphertext = ChaCha20Poly1305(wrapping_key).encrypt(wrap_nonce, content_key, _AAD)
        envelopes[str(user_id)] = {
            "ephemeral_public_key": _encode(ephemeral_private_key.public_key().public_bytes_raw()),
            "nonce": _encode(wrap_nonce),
            "ciphertext": _encode(ciphertext),
        }
    return encrypted_payload, envelopes


def _derive_key(shared_secret: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_AAD).derive(shared_secret)


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))
