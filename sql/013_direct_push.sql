CREATE TABLE IF NOT EXISTS push_devices (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    installation_id uuid NOT NULL,
    provider text NOT NULL CHECK (provider IN ('onesignal', 'fcm')),
    token text NOT NULL,
    token_hash text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT push_devices_installation_provider_key UNIQUE (installation_id, provider),
    CONSTRAINT push_devices_provider_token_key UNIQUE (provider, token_hash)
);
CREATE INDEX IF NOT EXISTS ix_push_devices_user_id ON push_devices(user_id);
CREATE TABLE IF NOT EXISTS push_deliveries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_id uuid REFERENCES notifications(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    device_id uuid REFERENCES push_devices(id) ON DELETE SET NULL,
    event_key text NOT NULL,
    provider text NOT NULL CHECK (provider IN ('onesignal', 'fcm')),
    token text NOT NULL,
    token_hash text NOT NULL,
    title text NOT NULL,
    body text NOT NULL,
    data jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'pending',
    attempts integer NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    accepted_at timestamptz,
    received_at timestamptz,
    provider_message_id text,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT push_deliveries_event_target_key UNIQUE (event_key, provider, token_hash)
);
CREATE INDEX IF NOT EXISTS ix_push_deliveries_user_id ON push_deliveries(user_id);
CREATE INDEX IF NOT EXISTS ix_push_deliveries_status ON push_deliveries(status);
CREATE INDEX IF NOT EXISTS ix_push_deliveries_next_attempt_at ON push_deliveries(next_attempt_at);
