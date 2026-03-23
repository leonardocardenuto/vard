BEGIN;

CREATE TABLE IF NOT EXISTS user_credentials (
    user_id uuid PRIMARY KEY REFERENCES app_users(id) ON DELETE CASCADE,
    password_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMIT;
