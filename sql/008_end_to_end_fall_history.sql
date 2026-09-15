ALTER TABLE app_users ADD COLUMN IF NOT EXISTS encryption_public_key TEXT;
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS encrypted_private_key_backup TEXT;
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS encryption_recovery_salt TEXT;
ALTER TABLE fall_events ALTER COLUMN occurred_at_encrypted DROP NOT NULL;
ALTER TABLE fall_events ADD COLUMN IF NOT EXISTS encrypted_payload TEXT;
ALTER TABLE fall_events ADD COLUMN IF NOT EXISTS key_envelopes JSONB NOT NULL DEFAULT '{}'::jsonb;
