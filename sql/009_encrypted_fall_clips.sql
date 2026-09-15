ALTER TABLE fall_events ADD COLUMN IF NOT EXISTS encrypted_clip_path TEXT;
ALTER TABLE fall_events ADD COLUMN IF NOT EXISTS clip_key_envelopes JSONB NOT NULL DEFAULT '{}'::jsonb;
