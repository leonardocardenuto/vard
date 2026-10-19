ALTER TABLE workspace_members DROP CONSTRAINT workspace_members_role_check;
ALTER TABLE workspace_members ADD CONSTRAINT workspace_members_role_check
CHECK (role IN ('owner', 'admin', 'member', 'caregiver', 'viewer', 'elderly'));

CREATE TABLE mobile_monitor_devices (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    token_hash text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz,
    last_seen_at timestamptz
);
CREATE INDEX ix_mobile_monitor_devices_user_id ON mobile_monitor_devices(user_id);
