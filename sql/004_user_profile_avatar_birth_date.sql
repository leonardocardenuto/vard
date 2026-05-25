BEGIN;

ALTER TABLE app_users
ADD COLUMN IF NOT EXISTS avatar_url text,
ADD COLUMN IF NOT EXISTS birth_date date;

COMMIT;
