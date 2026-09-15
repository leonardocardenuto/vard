import base64
import unittest
import uuid
from datetime import UTC, datetime

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from api.core.e2ee import encrypt_bytes_for_recipients, encrypt_for_recipients


class E2EEFallHistoryTests(unittest.TestCase):
    def test_server_cannot_read_timestamp_and_recipient_can(self):
        private_key = X25519PrivateKey.generate()
        user_id = uuid.uuid4()
        occurred_at = datetime(2026, 9, 12, 16, 42, 5, tzinfo=UTC)
        public_key = base64.urlsafe_b64encode(private_key.public_key().public_bytes_raw()).decode()

        payload, envelopes = encrypt_for_recipients(occurred_at, {user_id: public_key})

        self.assertNotIn("2026-09-12", payload)
        envelope = envelopes[str(user_id)]
        shared_secret = private_key.exchange(X25519PublicKey.from_public_bytes(base64.urlsafe_b64decode(envelope["ephemeral_public_key"])))
        key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"vard/fall-event/v2").derive(shared_secret)
        content_key = ChaCha20Poly1305(key).decrypt(base64.urlsafe_b64decode(envelope["nonce"]), base64.urlsafe_b64decode(envelope["ciphertext"]), b"vard/fall-event/v2")
        raw = base64.urlsafe_b64decode(payload)
        result = ChaCha20Poly1305(content_key).decrypt(raw[:12], raw[12:], b"vard/fall-event/v2")
        self.assertEqual(datetime.fromisoformat(result.decode()), occurred_at)

    def test_encrypts_a_clip_for_the_recipient(self):
        private_key = X25519PrivateKey.generate()
        user_id = uuid.uuid4()
        public_key = base64.urlsafe_b64encode(private_key.public_key().public_bytes_raw()).decode()
        clip = b"not-a-plain-video-in-storage"

        encrypted_clip, envelopes = encrypt_bytes_for_recipients(clip, {user_id: public_key})

        self.assertNotIn(clip, encrypted_clip)
        envelope = envelopes[str(user_id)]
        shared_secret = private_key.exchange(X25519PublicKey.from_public_bytes(base64.urlsafe_b64decode(envelope["ephemeral_public_key"])))
        key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"vard/fall-event/v2").derive(shared_secret)
        content_key = ChaCha20Poly1305(key).decrypt(base64.urlsafe_b64decode(envelope["nonce"]), base64.urlsafe_b64decode(envelope["ciphertext"]), b"vard/fall-event/v2")
        self.assertEqual(ChaCha20Poly1305(content_key).decrypt(encrypted_clip[:12], encrypted_clip[12:], b"vard/fall-event/v2"), clip)
