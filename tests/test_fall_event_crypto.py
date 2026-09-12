import unittest
import uuid
from datetime import UTC, datetime

from api.core.fall_event_crypto import (
    FallEventEncryptionError,
    decrypt_occurred_at,
    encrypt_occurred_at,
)


class FallEventCryptoTests(unittest.TestCase):
    encryption_key = "G5aCTfKrrzjMuZmi60NTJOIVSc48w4NqGj1zcYkToKk="

    def test_encrypts_the_exact_time_and_binds_it_to_workspace(self):
        workspace_id = uuid.uuid4()
        occurred_at = datetime(2026, 9, 12, 14, 30, 15, tzinfo=UTC)

        encrypted = encrypt_occurred_at(occurred_at, workspace_id, self.encryption_key)

        self.assertNotIn("2026-09-12", encrypted)
        self.assertEqual(decrypt_occurred_at(encrypted, workspace_id, self.encryption_key), occurred_at)
        with self.assertRaises(FallEventEncryptionError):
            decrypt_occurred_at(encrypted, uuid.uuid4(), self.encryption_key)


if __name__ == "__main__":
    unittest.main()
