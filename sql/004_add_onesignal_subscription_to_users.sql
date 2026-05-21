BEGIN;

ALTER TABLE app_users
ADD COLUMN IF NOT EXISTS onesignal_subscription_id text;

COMMIT;
