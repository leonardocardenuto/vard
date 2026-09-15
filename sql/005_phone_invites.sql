BEGIN;

-- Allow phone-based invites alongside email-based ones
ALTER TABLE workspace_invites ADD COLUMN IF NOT EXISTS phone text;
ALTER TABLE workspace_invites ALTER COLUMN email DROP NOT NULL;

ALTER TABLE workspace_invites
    ADD CONSTRAINT workspace_invites_email_or_phone_check
    CHECK (email IS NOT NULL OR phone IS NOT NULL);

-- Prevent duplicate pending invites for the same phone in a workspace
CREATE UNIQUE INDEX IF NOT EXISTS ux_workspace_invites_pending_phone
ON workspace_invites (workspace_id, phone)
WHERE status = 'pending' AND phone IS NOT NULL;

COMMIT;
